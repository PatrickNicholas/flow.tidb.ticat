#!/bin/env python3 
# encoding: utf-8

import fire
import csv

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
            row.qps,
            row.tps,
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


def main(host, database, user):
    config = {
      'user': user,
      'host': host,
      'database': database,
      'raise_on_warnings': True
    }

    conn = mysql.connector.connect(**config)
    curs = conn.cursor(named_tuple=True)
    # with open('{}-sysbench.csv'.format(database), 'w', newline='') as file:
    #     writer = csv.writer(file)
    #     _dump_sysbench(writer, curs)
    with open('{}-tpcc.csv'.format(database), 'w', newline='') as file:
        writer = csv.writer(file)
        _dump_tpcc(writer, curs)
    # with open('{}-ycsb.csv'.format(database), 'w', newline='') as file:
    #     writer = csv.writer(file)
    #     _dump_ycsb(writer, curs)
    curs.close()
    conn.close()
                

if __name__ == '__main__':
    fire.Fire()
