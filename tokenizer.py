"""GPT-2 byte-level BPE with local, verified OpenAI assets (GPT-2 MIT license)."""
from hashlib import sha256
from pathlib import Path

from tokenizers import Tokenizer, decoders, models, pre_tokenizers

ASSET_URL = "https://openaipublic.blob.core.windows.net/gpt-2/encodings/main/"
ASSETS = {
    "encoder.json": "196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783",
    "vocab.bpe": "1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5",
}
EOT = 50256


def load(directory=Path(__file__).parent / "data/tokenizer"):
    for name, expected in ASSETS.items():
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Tokenizer checksum mismatch: {name}")
    tokenizer = Tokenizer(models.BPE.from_file(str(directory / "encoder.json"),
                                                str(directory / "vocab.bpe")))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()
    if tokenizer.get_vocab_size() != EOT + 1 or tokenizer.token_to_id("<|endoftext|>") != EOT:
        raise ValueError("Unexpected GPT-2 vocabulary")
    return tokenizer


def document_ids(tokenizer, text):
    return tokenizer.encode(text).ids + [EOT]


if __name__ == "__main__":
    # An explicit provisioning command. Ordinary tokenization is entirely offline.
    from argparse import ArgumentParser
    from urllib.request import urlopen
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", required=True)
    args = parser.parse_args()
    directory = Path(__file__).parent / "data/tokenizer"
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in ASSETS.items():
        dest = directory / name
        if dest.exists() and sha256(dest.read_bytes()).hexdigest() == expected:
            continue
        with urlopen(ASSET_URL + name, timeout=30) as stream:
            body = stream.read(2 * 1024 * 1024)
        if sha256(body).hexdigest() != expected:
            raise ValueError(f"Upstream asset failed verification: {name}")
        temp = dest.with_suffix(".tmp")
        temp.write_bytes(body)
        temp.replace(dest)
    load(directory)
