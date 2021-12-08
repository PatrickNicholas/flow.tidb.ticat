set -euo pipefail

session="${1}"
env=`cat "${session}/env"`

host=`must_env_val "${env}" 'mysql.host'`
port=`must_env_val "${env}" 'mysql.port'`
user=`must_env_val "${env}" 'mysql.user'`

function my_exe()
{
	local query="${1}"
	mysql -h "${host}" -P "${port}" -u "${user}" --database=test -e "${query}"
}

my_exec "ALTER TABLE usertable ADD INDEX (FIELD0);"
