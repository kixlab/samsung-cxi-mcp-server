```
dataset/
├── batches/
│   └── generation/
│       ├── batch_1.txt
│       ├── batch_2.txt
│       ├── batch_3.txt
│       └── batches.yaml
├── benchmarks/
│   └── generation_gt/
│       ├── gid1-1-meta.json
│       ├── gid1-1-png.json
│       ├── gid1-2-meta.json
│       ├── gid1-2-png.json
│       └── ...

src
├── fastapi_server
│       └── ...
├── experiments
│   └── run_generation_experiment.py
└── ...

scripts
├── create_datataset_batch.py
└── ...

```

Make the batches with `python scripts/create_datataset_batch.py`.
After that,

## Generation Task
with batch
```
python -m experiments.run_generation_experiment \
  --model=gemini \
  --variants=image_only \
  --channel=channel_1 \
  --batch_name=batch_1 \
  --batches_config_path=dataset/batches/generation/batches.yaml
```

without batch
```
python -m experiments.run_generation_experiment \
  --model=gemini \
  --variants=image_only \
  --channel=channel_1
```

for failure case 
```
python -m experiments.run_generation_experiment \
  --model=gemini \
  --variants=image_only \
  --channel=channel_2 \
  --batch_name=error_image_only \
  --config_name=single-generation \
  --batches_config_path=../dataset/batches/generation/batches.yaml
```

## Modification Task
```
python -m experiments.run_modification_experiment \
  --config_name=single-modification \
  --task=task-1 \
  --model=gemini \
  --variants=without_oracle \
  --channel=channel_2 \
```