from flask import Flask, render_template, request
import torch
from src import models
from PIL import Image
import string
import random

app = Flask(__name__)
device = "cpu"
checkpoint = "./models/final_models.ckpt"
config = "./models/config.yaml"
model = models.StyleGAN(config, device, checkpoint)

        
@torch.no_grad()
def infer(model, prompt, n_samples, scale, skips=250):
    images, clip_score = model(prompt, n_samples_per_txt=n_samples, cond_scale=scale, skips=skips, clip_sort=True)
    images = images.cpu()
    make_im = lambda x: (255*x.clamp(-1, 1)/2 + 127.5).to(torch.uint8).permute(1,2,0).numpy()
    images = [Image.fromarray(make_im(x)) for x in images]
    return images, clip_score

def get_random_name():
    letters = string.ascii_lowercase
    result = []
    for j in range(15):
        result_str = ''.join(random.choice(letters) for i in range(10)) + ".jpg"
        result.append(result_str)
    return result

# @app.route("/")
# def hello():
#     return render_template("index.html")


@app.route("/", methods = ['GET', 'POST'])
def predict():
    if request.method == 'GET':
        return render_template("index.html")
    else:
        captions = request.form['caption']
        if not captions:
            return render_template("index.html")
        else:
            output, _ = infer(model, captions, 15, 4)
            file_name = get_random_name()
            for i in range(15):
                output[i].save("static/" + file_name[i])
            return render_template("index.html", result = file_name)

if __name__ == 'main':
    app.run()