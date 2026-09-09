# Child CI is not canonical

This snapshot mirrors a child repository. The canonical IMP CI lives at the
parent-monorepo root: `.github/workflows/imp-validate.yml` and
`.github/workflows/imp-python.yml`. Do not run or treat this directory as
canonical; syncs from the child may re-create files here.
