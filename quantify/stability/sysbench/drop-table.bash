set -euo pipefail
. "`cd $(dirname ${BASH_SOURCE[0]}) && pwd`/../../../helper/helper.bash"

session="${1}"
env=`cat "${session}/env"`

host=`must_env_val "${env}" 'mysql.host'`
port=`must_env_val "${env}" 'mysql.port'`
user=`must_env_val "${env}" 'mysql.user'`
from=`must_env_val "${env}" 'quantify.stability.drop-table.sysbench.from'`
to=`must_env_val "${env}" 'quantify.stability.drop-table.sysbench.to'`

function my_exec()
{
	local query="${1}"
	mysql -h "${host}" -P "${port}" -u "${user}" --database=test -e "${query}"
}

table_names=()
for id in $(seq ${from} ${to}); do
    table_names+=("sbtest${id}")
done

name_list=$(IFS=, ; echo "${table_names[*]}")
my_exec "DROP TABLE IF EXISTS ${name_list}"
