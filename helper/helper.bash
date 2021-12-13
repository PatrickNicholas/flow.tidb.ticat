. "`cd $(dirname ${BASH_SOURCE[0]}) && pwd`/ticat.helper.bash/helper.bash"

function timestamp()
{
	echo `date +%s`
}

function must_cluster_pd()
{
	local name="${1}"
	set +e
	local pd=`tiup cluster display "${name}" 2>/dev/null | \
		{ grep '\-\-\-\-\-\-\-$' -A 9999 || test $? = 1; } | \
		awk '{if ($2=="pd") print $1}'`
	set -e
	if [ -z "${pd}" ]; then
		echo "[:(] no pd found in cluster '${name}'" >&2
		exit 1
	fi
	echo "${pd}"
}

function generate_tikv_scale_out_yaml()
{
    local tikv_nodes="${1}"
    local yaml="/tmp/tikv_scale_out_$(timestamp).yaml"    
    echo 'tikv_servers:' >${yaml}
    for node in ${node//,/ }; do
        echo "  - ip: ${node}" >>${yaml}
    done
    echo "${yaml}"
}
