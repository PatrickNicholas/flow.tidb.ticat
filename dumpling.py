#!/bin/env python3
# encoding: utf-8

import fire

import os
import csv
import time
from datetime import datetime
import requests
import mysql.connector


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
        time.sleep(1)
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


def _send_notice(content):
    hook_id = os.getenv("NOTICE_HOOK_ID")
    url = 'https://open.feishu.cn/open-apis/bot/v2/hook/{}'.format(hook_id)
    headers = {'Content-Type': 'application/json' }
    payload = {
        'msg_type': 'text',
        'content': {
            'text': content,
        }
    }
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise IOError("request {}: {}, (code {})".format(url, r.text, r.status_code))


def _read_upload_files(filename):
    with open(filename, 'rb') as file:
        for line in file:
            line = line.strip(b'\n').decode('utf-8')
            if len(line.strip()) == 0 or line.startswith("#"):
                continue
            item = line.split(' ')
            if len(item) != 2:
                raise RuntimeError("unknown format {}".format(line))
            yield (item[0], item[1])


def upload(desc_file, with_date_prefix=True, send_notice=False):
    """
        Upload xls to feishu sheets

        The desc file format is:

        name1 path1
        name2 path2

        The <name> will be used as the part of title of sheets.
    """
    urls = []
    now = datetime.now()
    folder_token = '' # os.getenv('FOLDER_TOKEN')
    for (name, filename) in _read_upload_files(desc_file):
        with open(filename, 'rb') as file:
            title = name
            if with_date_prefix:
                title = now.strftime('%Y-%m-%d %H:%M-{}.csv'.format(name))
            content = file.read()
            urls.append((name, _upload_sheets(folder_token, title, [x for x in content])))
    
    content = 'OLTP test result: \n{}'.format('\n'.join(map(lambda n: ': '.join(n), urls )))
    print(content)
    if send_notice:
        _send_notice(urls)
                
                
def _unpack_params(values, abbr_map):
    result = {}
    for val in values:
        for key in abbr_map.keys():
            if val.startswith(key):
                result[abbr_map[key]] = val[len(key):]
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
    workload_abbr_map = {
        't': 'tables',
        's': 'table-rows',
    }
    conn_abbr_map = {
        't': 'threads',
        'd': 'duration',
    }
    
    result = {}
    result.update(_unpack_params(workload, workload_abbr_map))
    result.update(_unpack_params(conn, conn_abbr_map))
    return result


def _format_dict(params):
    return '\n'.join([ '{}={}'.format(k, v) for k, v in params.items() ])


class GenericTesting(object):
    def sysbench(writer, curs):
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
                row.qps,
                row.tps,
                row.min,
                row.avg,
                row.p95,
                row.max,
                _format_dict(params),
            ])
        
    
    def tpcc(writer, curs):
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
            

    def ycsb(writer, curs):
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
            

class StabilityTesting(object):
    def _write_event_jitter_header(writer):
        notes = "all values are about jitter"
        writer.writerow(['type', 'qps sd', 'p95 sd', 'p99 sd', 'p999 sd', 'qps max', 'p95 max', 'p99 max', 'p999 max', notes])


    def _write_event_jitter(writer, cursor, prefix, desc):
        sql = 'SELECT * FROM event_jitter WHERE prefix = "{}"'.format(prefix)
        cursor.execute(sql)
        for row in cursor:
            # lat95_jt_sd | lat95_jt_pos_max | lat99_jt_sd | lat99_jt_pos_max | lat999_jt_sd | lat999_jt_neg_max | qps_jt_sd | qps_jt_neg_max
            writer.writerow([
                desc,
                row.qps_jt_sd,
                row.lat95_jt_sd,
                row.lat99_jt_sd,
                row.lat999_jt_sd,
                row.qps_jt_neg_max,
                row.lat95_jt_pos_max,
                row.lat99_jt_pos_max,
                row.lat999_jt_neg_max,
                "-",
            ])
            
            
    def _write_event_duration_header(writer):
        writer.writerow(['type', 'duration(sec)'])

    
    def _write_event_duration(writer, cursor, event, tag, desc):
        sql = 'SELECT * FROM durations WHERE event = "{}" AND tag = "{}"'.format(event, tag)
        cursor.execute(sql)
        for row in cursor:
            writer.writerow([desc, row.duration_sec])

        
    def add_index(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.add-index", "add index")

    
    def drop_table(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.drop-table", "drop table")

    
    def backup(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.backup", "backup")

    
    def restart(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.restart", "restart")
        StabilityTesting._write_event_duration_header(writer)
        StabilityTesting._write_event_duration(writer, cursor, "tidb.reload", "restart", "restart")

    
    def scale(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.scale-in", "scale in")
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.scale-out", "scale out")
        StabilityTesting._write_event_duration_header(writer)
        StabilityTesting._write_event_duration(writer, cursor, "bench.scale-in", "scale-out-and-in", "scale in")
        StabilityTesting._write_event_duration(writer, cursor, "bench.scale-out", "scale-out-and-in", "scale out")
    

    def down(writer, cursor):
        StabilityTesting._write_event_jitter_header(writer)
        StabilityTesting._write_event_jitter(writer, cursor, "quantify.store-down", "store down")
        StabilityTesting._write_event_duration_header(writer)
        StabilityTesting._write_event_duration(writer, cursor, "tidb.watch.no-qps-jitter", "store-down", "qps jitter recovery")
        StabilityTesting._write_event_duration(writer, cursor, "tidb.watch.no-region", "store-down", "no region")
        

def dump(
    host, database, user,
    disable_all_generic=False,
    generic_tpcc=True, 
    generic_ycsb=True, 
    generic_sysbench=True, 
    disable_all_stability=False,
    stability_add_index=True, 
    stability_drop_table=True, 
    stability_backup=True, 
    stability_restart=True, 
    stability_scale=True, 
    stability_down=True):
    """
    Dump testing result from meta database
    
    This command will save result into files and print in screen in DESC format which would be useful in uploading.
    """
    testing = {}
    if not disable_all_generic:
        if generic_tpcc: testing['generic-tpcc'] = GenericTesting.tpcc
        if generic_sysbench: testing['generic-sysbench'] = GenericTesting.sysbench
        if generic_ycsb: testing['generic-ycsb'] = GenericTesting.tpcc
    if not disable_all_stability:
        if stability_add_index: testing['stability-add-index'] = StabilityTesting.add_index
        if stability_drop_table: testing['stability-drop-table'] = StabilityTesting.drop_table
        if stability_backup: testing['stability-backup'] = StabilityTesting.backup
        if stability_restart: testing['stability-restart'] = StabilityTesting.restart
        if stability_scale: testing['stability-scale'] = StabilityTesting.scale
        if stability_down: testing['stability-down'] = StabilityTesting.down

    config = {
      'user': user,
      'host': host,
      'database': database,
      'raise_on_warnings': True
    }

    files = {}
    conn = mysql.connector.connect(**config)
    curs = conn.cursor(named_tuple=True)
    for (name, method) in testing.items():
        files[name] = '/tmp/{}-{}.csv'.format(database, name)
        with open(files[name], 'w', newline='') as file:
            writer = csv.writer(file)
            method(writer, curs)
    curs.close()
    conn.close()

    for (name, url) in files.items():
        print("{} {}".format(name, url))


if __name__ == '__main__':
    fire.Fire()
