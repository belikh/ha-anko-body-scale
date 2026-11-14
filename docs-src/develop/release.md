---
title: Release
summary: Tag a version and let the release workflow publish the notes from CHANGELOG.md.
order: 20
audience: maintainers
status: draft
---

1. Add a `## <version>` section to `CHANGELOG.md`.
2. Set `version` in `custom_components/anko_scale/manifest.json` to the same value.
3. Push a tag named `<version>` or `v<version>`.

```sh title="Tag 2.0.1"
git tag v2.0.1
git push origin v2.0.1
```

The workflow `.github/workflows/release.yaml` copies the matching `CHANGELOG.md` section into the release body and attaches `manifest.json`. Without a matching section it generates the notes from the commits.

A tag with a hyphen, such as `2.1.0-rc.1`, publishes a pre-release. Its notes come from the section of the base version, `## 2.1.0`.

docs.jupiter.au reads the pages of the newest release and rebuilds once a day.

:::see-also
- [[develop/build-and-test]]
:::
