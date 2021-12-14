# flow.tidb.ticat


## Usage

### Prepare dataset

```
# prepare 1T dataset
ticat { <envs> } quantify.prepare.1t
# or prepare 10T dataset
ticat { <envs> } quantify.prepare.10t
```

### Run generic test (QPS & RT)

```
# quantify 1T dataset
ticat { <envs> } quantify.generic.1t
# or quantify 10T dataset
ticat { <envs> } quantify.generic.10t
```

You can change the running threads in `quantify/generic/config/<bench-tool>/workload.ticat`. For example, update sysbench threads by updating `quantify/generic/config/sysbench/workload.ticat`: 

```
[val2env]
bench.compare.threads = 200,300,400
```

### Run stability test

The stability test model is as follows:

- asynchronously start a bg job to perform certain operations, such as randomly kill a store
- start run workloads, and the workoad ends after a period of time
- statistics and records QPS & Latency jitter during the workload running period
- wait until bg job exit

Some background tasks will also record other metrics. For example, killing store will record the period of qps jitter recovery and the period all region is completely migrated.

#### Workloads

There already exists some prepared workload datasets in bucket `patrick` (http://minio.pingcap.net:9090/buckets/). You could config those workloads by:

```
ticat quantify.workloads.sysbench.1t
ticat quantify.workloads.tpcc.1t
ticat quantify.workloads.ycsb.1t
```

#### Simulate store down

You can run `quantify.stability.store-down` with workload config, for example:

```
ticat quantify.workloads.yscb.1t : quantify.stability.store-down
```

The result includes:

- QPS & Latency jitter during test
- The intervals QPS jitter is completely recoveried from killing store
- The intervals All regions is completely migrated from killing store

The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.store-down';
# query no-leader & no-region intervals
SELECT * FROM durations WHERE event = 'tidb.watch.no-qps-jitter' and tag = 'store-down';
SELECT * FROM durations WHERE event = 'tidb.watch.no-region' and tag = 'store-down';
```

#### Simulate rolling restart

You can run `quantify.stability.restart` with workload config like store down simulation. The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.restart';
# query reload duration
SELECT * FROM durations WHERE event = 'tidb.reload' and tag = 'restart';
```

The result includes:

- QPS & Latency jitter during test
- The intervals reload entrie pd and tikv nodes

#### Simulate add index

You can run `quantify.stability.add-index`, the default workload is ycsb 1T. You need to change the flow if you want to use different workload. Query result:

```
SELECT * FROM event_jitter WHERE prefix = 'quantify.add-index';
```

The result includes:

- QPS & Latency jitter during test

#### Simlulate drop table

You can run `quantify.stability.drop-table`, the default workload is sysbench 1T, the 1/10 tables will be dropped. You need to change the flow if you want to use different workload. Query result:

```
SELECT * FROM event_jitter WHERE prefix = 'quantify.drop-table';
```

The result includes:

- QPS & Latency jitter during test

#### Simulate backup

You can run `quantify.stability.backup` with workload config like store down simulation. The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.backup';
```

The result includes:

- QPS & Latency jitter during test

The data will backup into bucket `recycledaily` with prefix `recycledaily/backup/quantify_stability_backup_$(timestamp)`. This bucket will keep dataset 24hours before recycling.

#### Simulate scale in and scale out

You can run `quantify.stability.scale-in-and-out` with workload config like store down simulation. The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.scale-in';
SELECT * FROM event_jitter WHERE prefix = 'quantify.scale-out';
# query scale in duration
SELECT * FROM durations WHERE event = 'bench.scale-in' and tag = 'scale-out-and-in';
# query scale out duration
SELECT * FROM durations WHERE event = 'bench.scale-out' and tag = 'scale-out-and-in';
```

The result includes:

- QPS & Latency jitter during scale-in and scale-out
- The intervals from scale in to store balanced.
- The intervals from scale out to store balanced.

The default parameters will add one tikv node `tikv4-peer`, and scale in one tikv node randomly. You can specified the number of nodes by env:

- `quantify.stability.scale-out.nodes=peer4,peer5`
- `quantify.stability.scale-in.count=3`

### dump result and upload to docs
