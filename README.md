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

You can run `quantify.stability.restart` with workload config like store dowm simulation. The result is saved in meta database, could be queried by:

```
# query qps & latency jitter
SELECT * FROM event_jitter WHERE prefix = 'quantify.restart';
# query reload duration
SELECT * FROM durations WHERE event = 'tidb.reload' and tag = 'restart';
```


