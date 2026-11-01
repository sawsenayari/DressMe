"""Extracteurs d'embeddings d'images : CLIP ViT-B/32 ou histogramme couleur."""

from pathlib import Path

import numpy as np


def _dummy(imgs):
    out = []
    for im in imgs:
        a = np.asarray(im.convert("RGB").resize((32, 32)), dtype=float) / 255.0
        c = a[8:24, 8:24].reshape(-1, 3)
        h, _ = np.histogramdd(
            c, bins=(4, 4, 4), range=((0, 1), (0, 1), (0, 1))
        )
        out.append(
            np.concatenate(
                [h.ravel() / max(len(c), 1), c.mean(0), a.reshape(-1, 3).mean(0)]
            )
        )
    return np.asarray(out, dtype=np.float32)


def inject_lora(visual, num_blocks=2, rank=8, alpha=16):
    """Ajoute des adaptateurs LoRA aux MLP des derniers blocs du ViT.

    Les poids CLIP d'origine restent dans `base` et sont gelés.
    Seuls lora_A et lora_B sont entraînables.
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    blocks = list(visual.transformer.resblocks)
    if not 1 <= int(num_blocks) <= len(blocks):
        raise ValueError(
            f"num_blocks doit être entre 1 et {len(blocks)} (reçu {num_blocks})."
        )
    if int(rank) < 1:
        raise ValueError("rank doit être supérieur ou égal à 1.")

    class LoRALinear(nn.Module):
        def __init__(self, linear, r, lora_alpha):
            super().__init__()
            self.base = linear
            self.rank = int(r)
            self.scale = float(lora_alpha) / self.rank
            self.lora_A = nn.Parameter(
                torch.empty(self.rank, linear.in_features, device=linear.weight.device,
                            dtype=linear.weight.dtype)
            )
            self.lora_B = nn.Parameter(
                torch.zeros(linear.out_features, self.rank,
                            device=linear.weight.device, dtype=linear.weight.dtype)
            )
            nn.init.kaiming_uniform_(self.lora_A, a=5**0.5)
            for p in self.base.parameters():
                p.requires_grad = False

        def forward(self, x):
            update = F.linear(F.linear(x, self.lora_A), self.lora_B)
            return self.base(x) + update * self.scale

    # Avoid wrapping a layer twice if this helper is called repeatedly.
    for block in blocks[-int(num_blocks):]:
        mlp = block.mlp
        for attr in ("c_fc", "c_proj"):
            layer = getattr(mlp, attr)
            if not hasattr(layer, "lora_A"):
                setattr(mlp, attr, LoRALinear(layer, rank, alpha))

    return visual


def get_embedder(backend="clip", ft_path=None):
    """Retourne une fonction qui transforme une liste d'images en embeddings.

    `ft_path` accepte :
    - un checkpoint LoRA produit par training.vision ;
    - un ancien state_dict visuel brut.
    """
    if backend == "dummy":
        if ft_path:
            raise ValueError("Le backend 'dummy' ne prend pas en charge ft_path.")
        return _dummy

    if backend != "clip":
        raise ValueError(f"Backend inconnu : {backend!r}. Utilise 'clip' ou 'dummy'.")

    import torch
    import open_clip

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, pre = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )

    if ft_path:
        checkpoint = torch.load(ft_path, map_location="cpu", weights_only=False)

        if isinstance(checkpoint, dict) and "lora_state_dict" in checkpoint:
            inject_lora(
                model.visual,
                num_blocks=int(checkpoint.get("num_blocks", 2)),
                rank=int(checkpoint.get("rank", 8)),
                alpha=float(checkpoint.get("alpha", 16)),
            )
            missing, unexpected = model.visual.load_state_dict(
                checkpoint["lora_state_dict"], strict=False
            )
            # Only adapter keys should be missing from this partial checkpoint.
            unexpected_lora = [
                key for key in unexpected
                if "lora_A" in key or "lora_B" in key
            ]
            if unexpected_lora:
                raise RuntimeError(
                    f"Clés LoRA inattendues dans {ft_path}: {unexpected_lora}"
                )
        elif isinstance(checkpoint, dict) and "visual_state_dict" in checkpoint:
            # Compatibility with the previous checkpoint format.
            model.visual.load_state_dict(checkpoint["visual_state_dict"])
        else:
            # Compatibility with a raw visual state_dict.
            model.visual.load_state_dict(checkpoint)

    model.eval().to(dev)

    @torch.no_grad()
    def embed_images(imgs):
        if not imgs:
            return np.empty((0, model.visual.output_dim), dtype=np.float32)
        batch = torch.stack([pre(im.convert("RGB")) for im in imgs]).to(dev)
        z = model.encode_image(batch)
        z = z / z.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        return z.float().cpu().numpy()

    embed_images.model = model
    embed_images.pre = pre
    embed_images.dev = dev
    return embed_images
