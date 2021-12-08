set -euo pipefail
. "`cd $(dirname ${BASH_SOURCE[0]}) && pwd`/../../../helper/helper.bash"

session="${1}"
env=`cat "${session}/env"`

shift 1
key="${1}"
value="${2}"
from_env="${3}"

if [[ `to_true "${from_env}"` == "true" ]]; then
    value=`must_env_val "${env}" "${value}"`
fi

echo "${key}=${value}" >> "${session}/env"
