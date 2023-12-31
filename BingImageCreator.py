import contextlib
import os
import random
import time
from functools import partial
from typing import Dict
from typing import List
from typing import Union

import regex
import requests

BING_URL = os.getenv("BING_URL", "https://www.bing.com")
# Generate random IP between range 13.104.0.0/14
FORWARDED_IP = (
    f"13.{random.randint(104, 107)}.{random.randint(0, 255)}.{random.randint(0, 255)}"
)
HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "content-type": "application/x-www-form-urlencoded",
    "referrer": "https://www.bing.com/images/create/",
    "origin": "https://www.bing.com",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.63",
    "x-forwarded-for": FORWARDED_IP,
}

# Error messages
error_timeout = "Your request has timed out."
error_redirect = "Redirect failed"
error_blocked_prompt = (
    "Your prompt has been blocked by Bing. Try to change any bad words and try again."
)
error_being_reviewed_prompt = "Your prompt is being reviewed by Bing. Try to change any sensitive words and try again."
error_noresults = "Could not get results"
error_unsupported_lang = "\nthis language is currently not supported by bing"
error_bad_images = "Bad images"
error_no_images = "No images"
# Action messages
sending_message = "Sending request..."
wait_message = "Waiting for results..."
download_message = "\nDownloading images..."



class ImageGen:
    """
    Image generation by Microsoft Bing
    Parameters:
        auth_cookie: str
        auth_cookie_SRCHHPGUSR: str
    """

    def __init__(
        self,
        auth_cookie: str,
        auth_cookie_SRCHHPGUSR: str,
        proxy=None,
    ) -> None:
        self.session: requests.Session = requests.Session()
        self.session.headers = HEADERS
        self.session.cookies.set("_U", auth_cookie)
        self.session.cookies.set("SRCHHPGUSR", auth_cookie_SRCHHPGUSR)
        if proxy is not None:
            self.session.proxies = proxy
        # proxy = {"http": "http://127.0.0.1:7890", "https": "https://127.0.0.1:7890"}
        # self.session.proxies = proxy

    def get_images(self, prompt: str) -> list:
        """
        Fetches image links from Bing
        Parameters:
            prompt: str
        """
        
        print(sending_message)
        url_encoded_prompt = requests.utils.quote(prompt)
        payload = f"q={url_encoded_prompt}&qs=ds"
        # https://www.bing.com/images/create?q=<PROMPT>&rt=3&FORM=GENCRE
        url = f"{BING_URL}/images/create?q={url_encoded_prompt}&rt=4&FORM=GENCRE"
        response = self.session.post(
            url,
            allow_redirects=False,
            data=payload,
            timeout=200,
        )
        # check for content waring message
        if "this prompt is being reviewed" in response.text.lower():
            raise Exception(
                error_being_reviewed_prompt,
            )
        if "this prompt has been blocked" in response.text.lower():
            raise Exception(
                error_blocked_prompt,
            )
        if (
            "we're working hard to offer image creator in more languages"
            in response.text.lower()
        ):
            raise Exception(error_unsupported_lang)
        if response.status_code != 302:
            # if rt4 fails, try rt3
            url = f"{BING_URL}/images/create?q={url_encoded_prompt}&rt=3&FORM=GENCRE"
            response = self.session.post(url, allow_redirects=False, timeout=200)
            if response.status_code != 302:
                print(f"ERROR: {response.text}")
                raise Exception(error_redirect)
        # Get redirect URL
        redirect_url = response.headers["Location"].replace("&nfy=1", "")
        request_id = redirect_url.split("id=")[-1]
        self.session.get(f"{BING_URL}{redirect_url}")
        # https://www.bing.com/images/create/async/results/{ID}?q={PROMPT}
        polling_url = f"{BING_URL}/images/create/async/results/{request_id}?q={url_encoded_prompt}"
        # Poll for results
        print("Waiting for results...")
        start_wait = time.time()
        while True:
            if int(time.time() - start_wait) > 200:
                raise Exception(error_timeout)
            print(".", end="", flush=True)
            response = self.session.get(polling_url)
            if response.status_code != 200:
                raise Exception(error_noresults)
            if not response.text or response.text.find("errorMessage") != -1:
                time.sleep(1)
                continue
            else:
                break
        # Use regex to search for src=""
        image_links = regex.findall(r'src="([^"]+)"', response.text)
        # Remove size limit
        normal_image_links = [link.split("?w=")[0] for link in image_links]
        # Remove duplicates
        normal_image_links = list(set(normal_image_links))

        # Bad images
        bad_images = [
            "https://r.bing.com/rp/in-2zU3AJUdkgFe7ZKv19yPBHVs.png",
            "https://r.bing.com/rp/TX9QuO3WzcCJz1uaaSwQAz39Kb0.jpg",
        ]
        for img in normal_image_links:
            if img in bad_images:
                raise Exception("Bad images")
        # No images
        if not normal_image_links:
            raise Exception(error_no_images)
        return normal_image_links

    def save_images(
        self,
        links: list,
        output_dir: str = "out",
        file_name: str = None,
        download_count: int = None,
    ) -> None:
        """
        Saves images to output directory
        Parameters:
            links: list[str]
            output_dir: str
            file_name: str
            download_count: int
        """
        print(download_message)
        with contextlib.suppress(FileExistsError):
            os.mkdir(output_dir)
        try:
            fn = f"{file_name}_" if file_name else ""
            jpeg_index = 0

            if download_count:
                links = links[:download_count]

            for link in links:
                while os.path.exists(
                    os.path.join(output_dir, f"{fn}{jpeg_index}.jpeg")
                ):
                    jpeg_index += 1
                response = self.session.get(link)
                if response.status_code != 200:
                    raise Exception("Could not download image")
                # save response to file
                with open(
                    os.path.join(output_dir, f"{fn}{jpeg_index}.jpeg"), "wb"
                ) as output_file:
                    output_file.write(response.content)
                jpeg_index += 1

        except requests.exceptions.MissingSchema as url_exception:
            raise Exception(
                "Inappropriate contents found in the generated images. Please try again or try another prompt.",
            ) from url_exception
