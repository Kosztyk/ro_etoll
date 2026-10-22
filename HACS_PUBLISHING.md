# RO eToll — Publication in HACS

1. Verify HACS, Hassfest and Packaging checks on the preparation PR.
2. Merge into main after checks pass, then validate the main push.
3. The release workflow publishes v1.0.2 only after the main push validation
   succeeds. If it cannot publish, create a full GitHub Release manually
   targeting that validated commit.
4. Confirm the release was published after successful validation.
5. Test in HACS > Custom repositories, type Integration, using
   https://github.com/Kosztyk/ro_etoll
6. In the Kosztyk/default fork, add "Kosztyk/ro_etoll" to the alphabetical
   integration catalog on a new branch from master.
7. Submit a PR to hacs/default:master using the official template. Check
   all six boxes and supply links to the exact GitHub Release and the
   passing HACS and Hassfest jobs.

Don't request maintainer reviews or create duplicate HACS submissions.
Publication requirements: https://www.hacs.xyz/docs/publish/start/
