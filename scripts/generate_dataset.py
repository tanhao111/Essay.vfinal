# Generate datasets
from multiprocessing import Process
import multiprocessing as mp
import math
from functools import partial
from pathlib import Path

import numpy as np
import torch
import typer
from joblib import Parallel, delayed
from PIL import Image
from tqdm import tqdm
import torch.nn.functional as F

from src.models import Clipper, load_sg


import multiprocessing as mp
try:
    mp.set_start_method('spawn')
except:
    pass

generators = {
    "sg2-ffhq-1024": partial(load_sg, 'https://api.ngc.nvidia.com/v2/models/nvidia/research/stylegan2/versions/1/files/stylegan2-ffhq-1024x1024.pkl'),
    "sg3-lhq-256": partial(load_sg, 'https://huggingface.co/justinpinkney/stylegan3-t-lhq-256/resolve/main/lhq-256-stylegan3-t-25Mimg.pkl'),
}


def mix_styles(w_batch, space):
    space_spec = {
        "w3": (4, 4, 10),
    }
    latent_mix = space_spec[space]

    bs = w_batch.shape[0]
    spec = torch.tensor(latent_mix).to(w_batch.device)

    index = torch.randint(0,bs, (len(spec),bs)).to(w_batch.device)
    return w_batch[index, 0, :].permute(1,0,2).repeat_interleave(spec, dim=1), spec

@torch.no_grad()
def run_folder_list(
    device_index,
    out_dir,
    generator_name,
    feature_extractor_name,
    out_image_size,
    batch_size,
    n_save_workers,
    samples_per_folder,
    folder_indexes,
    space="w",
    save_im=True,
    ):
    """Generate a directory of generated images and correspdonding embeddings and latents"""
    latent_dim = 512
    device = f"cuda:{device_index}"
    typer.echo(device_index)

    typer.echo("Loading generator")
    G = generators[generator_name]().to(device).eval()

    typer.echo("Loading feature extractor")
    feature_extractor = Clipper(feature_extractor_name).to(device)

    typer.echo("Generating samples")
    typer.echo(f"using space {space}")

    with Parallel(n_jobs=n_save_workers, prefer="threads") as parallel:
        for i_folder in folder_indexes:
            folder_name = out_dir/f"{i_folder:05d}"
            folder_name.mkdir(exist_ok=True)

            z = torch.randn(samples_per_folder, latent_dim, device=device)
            w = G.mapping(z, c=None)
            ds = torch.utils.data.TensorDataset(w)
            loader = torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=False, drop_last=False)
            for batch_idx, batch in enumerate(tqdm(loader, position=device_index)):
                if space == "w":
                    this_w = batch[0].to(device)
                    latents = this_w[:,0,:].cpu().numpy()
                else:
                    this_w, select_idxs = mix_styles(batch[0].to(device), space)
                    latents = this_w[:,select_idxs,:].cpu().numpy()

                out = G.synthesis(this_w)

                out = F.interpolate(out, (out_image_size,out_image_size), mode="area")
                image_features = feature_extractor.embed_image(out)
                image_features = image_features.cpu().numpy()

                if save_im:
                    out = out.permute(0,2,3,1).clamp(-1,1)
                    out = (255*(out*0.5 + 0.5).cpu().numpy()).astype(np.uint8)
                else:
                    out = [None]*len(latents)
                parallel(
                    delayed(process_and_save)(batch_size, folder_name, batch_idx, idx, latent, im, image_feature, save_im)
                    for idx, (latent, im, image_feature) in enumerate(zip(latents, out, image_features))
                    )

    typer.echo("finished folder")


def process_and_save(batch_size, folder_name, batch_idx, idx, latent, im, image_feature, save_im):
    count = batch_idx*batch_size + idx
    basename = folder_name/f"{folder_name.stem}{count:04}"
    np.save(basename.with_suffix("latent.npy"), latent)
    np.save(basename.with_suffix("image_feat.npy"), image_feature)
    if save_im:
        im = Image.fromarray(im)
        im.save(basename.with_suffix(".gen.jpg"), quality=95)

def make_webdataset(in_dir, out_dir):
    import tarfile
    in_folders = [x for x in Path(in_dir).glob("*") if x.is_dir]
    out_dir = Path(out_dir)
    out_dir.mkdir()
    for folder in in_folders:
        filename = out_dir/f"{folder.stem}.tar"
        files_to_add = sorted(list(folder.rglob("*")))

        with tarfile.open(filename, "w") as tar:
            for f in files_to_add:
                tar.add(f)


def main(
    out_dir:Path,
    n_samples:int=1_000_000,
    generator_name:str="sg2-ffhq-1024", # Key into `generators` dict`
    feature_extractor_name:str="ViT-B/32",
    n_gpus:int=2,
    out_image_size:int=256,
    batch_size:int=32,
    n_save_workers:int=16,
    space:str="w",
    samples_per_folder:int=10_000,
    save_im:bool=False, # Save the generated images?
    ):
    typer.echo("starting")

    out_dir.mkdir(parents=True)

    n_folders = math.ceil(n_samples/samples_per_folder)
    folder_indexes = range(n_folders)

    sub_indexes = np.array_split(folder_indexes, n_gpus)

    processes = []
    for dev_idx, folder_list in enumerate(sub_indexes):
        p = Process(
            target=run_folder_list,
            args=(
                dev_idx,
                out_dir,
                generator_name,
                feature_extractor_name,
                out_image_size,
                batch_size,
                n_save_workers,
                samples_per_folder,
                folder_list,
                space,
                save_im,
                ),
            )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    typer.echo("finished all")

if __name__ == "__main__":
    # mp.set_start_method('spawn')
    typer.run(main)
