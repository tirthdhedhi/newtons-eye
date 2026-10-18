"""mlx_lm.lora with stability fixes for 7B models (their loss went NaN without them).

* The 4-bit checkpoint stores scales, biases and norms in float16, and Qwen2.5-7B overflows
  float16 activations (that was the NaN). They are cast to float32 at load time (bfloat16
  trained unstably).
* LoRA weights are float32 (the base model stays quantized, in its own dtype).
* Gradients are clipped to a global norm of ``CLIP`` before each Adam update.

Usage is identical to ``python -m mlx_lm.lora``:  python train_mlx.py --model ... --train --data ...
"""

import mlx.core as mx
import mlx.optimizers as optim
import mlx_lm.lora as lora
from mlx.utils import tree_map

CLIP = 1.0


class ClippedAdam(optim.Adam):
    def apply_gradients(self, gradients, parameters):
        gradients, _ = optim.clip_grad_norm(gradients, CLIP)
        return super().apply_gradients(gradients, parameters)


optim.Adam = ClippedAdam
_convert = lora.linear_to_lora_layers


def _convert_fp32(model, num_layers, config, use_dora=False):
    _convert(model, num_layers, config, use_dora)
    model.update(tree_map(lambda p: p.astype(mx.float32), model.trainable_parameters()))


lora.linear_to_lora_layers = _convert_fp32
_load = lora.load


def _load_bf16(*args, **kwargs):
    model, tokenizer, *rest = _load(*args, **kwargs)
    model.update(
        tree_map(lambda p: p.astype(mx.float32) if p.dtype == mx.float16 else p, model.parameters())
    )
    return (model, tokenizer, *rest)


lora.load = _load_bf16

if __name__ == "__main__":
    lora.main()
