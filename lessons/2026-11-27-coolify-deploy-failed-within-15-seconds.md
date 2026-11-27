target: aiventure3d
role: implement
step: deploy
seen: 1
first_run: aiventure3d-1-20261127-1144
---
**What happened:** The image build of commit 4eece86 failed on the server 15 seconds after it started, and the merge was reverted. `client/src/world/testkit.ts` imports `../../../json/campaign.json`; the client stage of the Dockerfile copied only `client/`, and `pnpm build` type-checks the tests, so the import could not be resolved in the image. Every local gate had passed because the file exists in the checkout.

**Cause:** The Dockerfile listed the build inputs by hand and nothing built the image before the merge.

**Rule:** When code imports or reads a file from a folder the Dockerfile stage does not copy, add the COPY line in the same change, and run `podman build -q -t aiventure3d-gate .` before reporting done.
