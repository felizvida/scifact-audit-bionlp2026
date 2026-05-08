# SciFact dataset

The SciFact dataset is **not vendored** in this repository. To fetch it:

```bash
bash data/download_scifact.sh
```

This downloads `data.tar.gz` from `https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz` (~50 MB) and extracts it to `data/scifact/`.

After download you will have:

```
data/scifact/
├── claims_train.jsonl  (809 claims)
├── claims_dev.jsonl    (300 claims; 209 with gold evidence are the audit subset)
├── claims_test.jsonl   (300 hidden test claims; not used in this work)
└── corpus.jsonl        (5183 abstracts)
```

The audit pairs are derived by joining `claims_dev.jsonl` with `corpus.jsonl` on the `evidence` field of each claim. See `revision/build_packets.py` and `revision/run_haiku_experiments.py` for the join logic.

**Source citation:**

```bibtex
@inproceedings{wadden2020fact,
  title     = {Fact or Fiction: Verifying Scientific Claims},
  author    = {Wadden, David and Lin, Shanchuan and Lo, Kyle and Wang, Lucy Lu and van Zuylen, Madeleine and Cohan, Arman and Hajishirzi, Hannaneh},
  booktitle = {Proceedings of EMNLP},
  pages     = {7534--7550},
  year      = {2020},
  doi       = {10.18653/v1/2020.emnlp-main.609}
}
```
