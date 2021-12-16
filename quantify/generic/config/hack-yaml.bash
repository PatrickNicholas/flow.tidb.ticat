session="${1}"
yaml="${2}"

sed -i 's/   - host: tikv/  - host: tikv/g' "${yaml}"
