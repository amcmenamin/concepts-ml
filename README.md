# concepts-ml

Experiments with geospatial foundation-model embeddings. The repository has two
independent workflows:

- [aef](aef/README.md): compare Google AlphaEarth Foundation embeddings from two
	dates to locate potential change.
- [clay-trial](clay-trial/README.md): prepare imagery, create Clay embeddings,
	and explore them with clustering, similarity search, PCA, and UMAP.

## Setup

Use Python 3.11 or later. Install the project dependencies from the repository
root:

```powershell
uv sync
```

The Clay workflow also needs the Clay model checkpoint, `clay-v1.5.ckpt`, placed
where the processing scripts can find it. See the workflow-specific READMEs for
details and commands.