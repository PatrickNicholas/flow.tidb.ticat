#!/bin/env python3 
# encoding: utf-8

from time import sleep, strftime
from datetime import datetime
import fire
import csv
import requests
import os

import mysql.connector


def _unpack_params(values, abbrs):
    result = {}
    for val in values:
        for key in abbrs.keys():
            if val.startswith(key):
                result[abbrs[key]] = val[len(key):]
    return result


def _unpack_sysbench_workload_name(n):
    return {
        'ps': 'oltp_point_select',
        'i': 'oltp_insert',
        'd': 'oltp_delete',
        'ro': 'oltp_read_only',
        'rw': 'oltp_read_write',
        'rw': 'oltp_read_write',
        'ui': 'oltp_update_index',
        'uni': 'oltp_update_non_index',
        'wo': 'oltp_write_only',
    }[n]
    

def _unpack_sysbench_params(workload, conn):
    workload_abbrs = {
        't': 'tables',
        's': 'table-rows',
    }
    conn_abbrs = {
        't': 'threads',
        'd': 'duration',
    }
    
    result = {}
    result.update(_unpack_params(workload, workload_abbrs))
    result.update(_unpack_params(conn, conn_abbrs))
    return result


def _format_dict(params):
    return '\n'.join([ '{}={}'.format(k, v) for k, v in params.items() ])


def _dump_sysbench(writer, curs):
    writer.writerow(['workload', 'qps', 'tps', 'min(ms)', 'avg(ms)', 'p95(ms)', 'max(ms)', 'notes'])
    query = 'select * from sysbench';
    curs.execute(query)
    for row in curs:
        _, _, workload, concurrency = row.tag.split('@')
        workload_params = workload.split('-')
        concurrency_params = concurrency.split('-')
        workload_name = _unpack_sysbench_workload_name(workload_params[0])
        params = _unpack_sysbench_params(workload_params[1:], concurrency_params)
        writer.writerow([
            workload_name,
            round(row.qps / 600, 2),
            round(row.tps / 600, 2),
            row.min,
            row.avg,
            row.p95,
            row.max,
            _format_dict(params),
        ])
        

def _dump_tpcc(writer, curs):
    writer.writerow(['type', 'ops', 'avg(ms)', 'p50(ms)', 'p90(ms)', 'p95(ms)', 'p99(ms)', 'p999(ms)', 'max(ms)', 'notes'])
    query = 'select * from tpcc'
    curs.execute(query)
    for row in curs:
        if row.type.endswith('_ERR'):
            continue
        _, _, workload, concurrency = row.tag.split('@')
        _, warehouse = workload.split('-')
        concurrency_params = concurrency.split('-')
        params = _unpack_params(concurrency_params, {'t': 'threads', 'd': 'duration'})
        params['warehouse'] = warehouse
        writer.writerow([
            row.type,
            round(row.count / row.takes, 2),
            row.avg, 
            row.p50,
            row.p90,
            row.p95,
            row.p99,
            row.p999,
            row.max,
            _format_dict(params)
        ])
        

def _dump_ycsb(writer, curs):
    writer.writerow(['workload', 'type', 'ops', 'avg(us)', 'p99(us)', 'p999(us)', 'p9999(us)', 'min(us)', 'max(us)', 'notes'])
    query = 'select * from ycsb'
    curs.execute(query)
    for row in curs:
        _, _, _, params = row.tag.split('@')
        params = params.split('-')
        workload_name = params[0]
        if workload_name.startswith('orkload'):
            # fix bug
            workload_name = 'w' + workload_name
        params = _unpack_params(params[1:], {
            't': 'threads',
            'n': 'record-count',
            'ic': 'insert-count',
            'oc': 'operation-count',
        })
        writer.writerow([
            workload_name,
            row.type,
            row.ops,
            row.avg, 
            row.p99,
            row.p999,
            row.p9999,
            row.min,
            row.max,
            _format_dict(params)
        ])
        

_ACCESS_TOKEN = None

def _validate_resp(url, r, expect=0):
    if r.status_code != 200:
        raise IOError("request {}: {}, (code {})".format(url, r.text, r.status_code))

    value = r.json()
    if value.get('code') != 0 and value.get('code') != expect:
        raise RuntimeError("request {}: {}, (code {})".format(
            url, value.get('msg'), value.get('code')))
    return value


def _get_access_token():
    global _ACCESS_TOKEN
    if _ACCESS_TOKEN is not None:
        return _ACCESS_TOKEN

    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    payload = {
        'app_id': os.getenv('APP_ID'),
        'app_secret': os.getenv('APP_SECRET'),
    }
    r = requests.post(url, json=payload, headers=headers)
    value = _validate_resp(url, r)
    _ACCESS_TOKEN = 'Bearer {}'.format(value['tenant_access_token'])
    return _ACCESS_TOKEN

    
def _query_import_url(ticket):
    url = 'https://open.feishu.cn/open-apis/sheets/v2/import/result'
    payload = {'ticket': ticket}
    headers = {'Authorization': _get_access_token()}
    r = requests.get(url, params=payload, headers=headers)
    resp = _validate_resp(url, r, expect=90228)
    if resp.get('code') == 90228:
        # in progress
        sleep(1)
        return _query_import_url(ticket)

    data = resp.get('data', {})
    if data.get('warningCode') != 0:
        raise RuntimeError("query import result: {}", resp.get('warningCode'))
    return data.get('url')


def _upload_sheets(folder_token, name, content):
    url = 'https://open.feishu.cn/open-apis/sheets/v2/import'
    headers = {'Authorization': _get_access_token()}
    payload = {
        'name': name,
        'file': content,
        'folderToken': folder_token,
    }
    r = requests.post(url, json=payload, headers=headers)
    resp = _validate_resp(url, r)
    data = resp.get('data', {})
    ticket = data.get('ticket')
    return _query_import_url(ticket)


def _query_app_root_meta():
    url = 'https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta'
    headers = {'Authorization': _get_access_token()}
    r = requests.get(url, headers=headers)
    resp = _validate_resp(url, r)
    data = resp.get('data', {})
    return data.get('token')


def _send_notice(urls):
    hook_id = os.getenv("NOTICE_HOOK_ID")
    url = 'https://open.feishu.cn/open-apis/bot/v2/hook/{}'.format(hook_id)
    headers = {'Content-Type': 'application/json' }
    payload = {
        'msg_type': 'text',
        'content': {
            'text': 'OLTP generic test result (QPS & RT): \n{}'.format('\n'.join(urls)),
        }
    }
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise IOError("request {}: {}, (code {})".format(url, r.text, r.status_code))
    

def main(host, database, user, upload=False):
    config = {
      'user': user,
      'host': host,
      'database': database,
      'raise_on_warnings': True
    }
    
    mapping = {   # comp => method
        "sysbench": _dump_sysbench,
        # "tpcc": _dump_tpcc,
        # "ycsb": _dump_ycsb,
    }

    files = {}
    conn = mysql.connector.connect(**config)
    curs = conn.cursor(named_tuple=True)
    for (comp, method) in mapping.items():
        files[comp] = '/tmp/{}-{}.csv'.format(database, comp)
        with open(files[comp], 'w', newline='') as file:
            writer = csv.writer(file)
            method(writer, curs)
    curs.close()
    conn.close()
    
    if not upload:
        return

    urls = []
    now = datetime.now()
    folder_token = '' # os.getenv('FOLDER_TOKEN') # query_app_root_meta()
    for (comp, filename) in files.items():
        with open(filename, 'rb') as file:
            name = now.strftime('%Y-%m-%d %H:%M-generic-{}.csv'.format(comp))
            content = file.read()
            urls.append(_upload_sheets(folder_token, name, [x for x in content]))
    
    _send_notice(urls)
                
    for (_, name) in files.items():
        os.remove(name)


if __name__ == '__main__':
    fire.Fire()
