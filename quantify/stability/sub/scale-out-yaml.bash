set -euo pipefail
. "`cd $(dirname ${BASH_SOURCE[0]}) && pwd`/../../../helper/helper.bash"

session="${1}"
env=`cat "${session}/env"`

shift

nodes="${1}"
name=`must_env_val "${env}" 'tidb.cluster'`
yaml="`generate_tikv_scale_out_yaml ${nodes}`"

echo "tidb.tiup.yaml=${yaml}" >> "${session}/env"
