#!/bin/zsh
# usage: deploy_r2.sh [--dry-run] <model-dir> <bucket> <account-id>
# needs AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (R2 token) in env; aws-cli installed.
set -e
DRY=0; [[ $1 == --dry-run ]] && { DRY=1; shift; }
M=${1:?model-dir}; B=${2:?bucket}; A=${3:?account-id}
[[ -f $M/index.html && -f $M/runtime.css && -d $M/fonts ]] || { echo "bad model dir"; exit 1; }
[[ $DRY == 1 ]] || { [[ -n $AWS_ACCESS_KEY_ID && -n $AWS_SECRET_ACCESS_KEY ]] || { echo "set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"; exit 1; }; }
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_DEFAULT_REGION=auto
EP=https://$A.r2.cloudflarestorage.com
IMM='public, max-age=31536000, immutable'
run(){ if [[ $DRY == 1 ]]; then echo "+ $*"; else "$@"; fi }
S3=(aws s3 cp --endpoint-url $EP)
run $S3 $M/fonts s3://$B/fonts --recursive --exclude '*' --include '*.woff2' --content-type font/woff2 --cache-control "$IMM"
run $S3 $M/fonts s3://$B/fonts --recursive --exclude '*' --include '*.ttf' --content-type font/ttf --cache-control "$IMM"
run $S3 $M/runtime.css s3://$B/runtime.css --content-type 'text/css; charset=utf-8' --cache-control 'public, max-age=300'
[[ -f $M/README.txt ]] && run $S3 $M/README.txt s3://$B/README.txt --content-type 'text/plain; charset=utf-8' --cache-control 'public, max-age=300'
run $S3 $M/index.html s3://$B/index.html --content-type 'text/html; charset=utf-8' --cache-control 'public, max-age=300'
echo done
