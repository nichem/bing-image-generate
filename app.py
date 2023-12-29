from flask import Flask, request, jsonify
import os
from BingImageCreator import ImageGen

app = Flask(__name__)


@app.route("/gen_image", methods=["GET"])
def get_images():
    response = {"err": "0", "data": []}
    try:
        u = request.args.get("u")
        if not u:
            raise Exception("缺少参数u")
        s = request.args.get("s")
        if not s:
            raise Exception("缺少参数s")
        prompt = request.args.get("p")
        if not prompt:
            raise Exception("缺少参数p")
        imageGen = ImageGen(u, s)
        list = imageGen.get_images(prompt)
        response["data"] = list
        return jsonify(response)
    except Exception as e:
        response["err"] = str(e)
        return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=1236), host="0.0.0.0")
