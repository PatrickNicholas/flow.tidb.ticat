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

#### Simulate store down

You can run `quantify.stability.store-down` with workload config, for example:

```
ticat quantify.workloads.yscb.1t : quantify.stability.store-down
```

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

#### Simulate add index

You can run `quantify.stability.add-index`, the default workload is ycsb 1T. You need to change the flow if you want to use different workload. Query result:

```
SELECT * FROM event_jitter WHERE prefix = 'quantify.add-index';
```

#### Simlulate drop table

You can run `quantify.stability.drop-table`, the default workload is sysbench 1T, the 1/10 tables will be dropped. You need to change the flow if you want to use different workload. Query result:

```
SELECT * FROM event_jitter WHERE prefix = 'quantify.drop-table';
```

#### Simulate backup

You can run `quantify.stability.backup` with workload config like store down simulation. The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.backup';
```
