import yaml
from pathlib import Path

benchmark_dir = Path("dataset/benchmarks/generation_gt")
batch_output_dir = Path("dataset/batches/generation")
# benchmark_dir = Path("dataset/benchmarks/modification_gt")
# batch_output_dir = Path("dataset/batches/modification")

batch_output_dir.mkdir(parents=True, exist_ok=True)

meta_files = sorted(benchmark_dir.glob("gid*-meta.json"))
base_ids = [f.stem.replace("-meta", "") for f in meta_files]

batch_size = 100
num_batches = (len(base_ids) + batch_size - 1) // batch_size

batches_yaml = {"batches": {}}

for i in range(num_batches):
    batch_name = f"batch_{i+1}"
    batch_ids = base_ids[i * batch_size : (i + 1) * batch_size]
    batch_txt_path = batch_output_dir / f"{batch_name}.txt"

    with open(batch_txt_path, "w") as f:
        f.write("\n".join(batch_ids))

    batches_yaml["batches"][batch_name] = str(batch_txt_path)

batches_yaml_path = batch_output_dir / "batches.yaml"
with open(batches_yaml_path, "w") as f:
    yaml.dump(batches_yaml, f, sort_keys=False, allow_unicode=True)

print(f"✅ Created {num_batches} batches at {batch_output_dir}")
print(f"📄 YAML summary: {batches_yaml_path}")
