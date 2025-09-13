# Chango Components


## Component Version


| Component                                              | Version            | 
|:-------------------------------------------------------|:-------------------| 
| Apache Ozone                                           | 1.3.0              | 
| Kafka                                                  | 3.6.x              | 
| Zookeeper                                              | 3.6.4              | 
| Schema Registry                                        | 7.6.1              | 
| Spark                                                  | 3.4.3 / Scala 2.12 | 
| Livy                                                   | 0.8.0-incubating   | 
| Trino                                                  | 452                | 
| Iceberg                                                | 1.5.2              | 
| Open JDK                                               | 8 / 17 / 22        | 
| Azkaban                                                | 3.90.0             | 
| Azkaban CLI                                            | 0.9.14             |
| Superset                                               | 0.38.1             |
| OpenSearch                                             | 2.19.3              |
| Chango Admin                                           | 2.7.0              | 
| Chango Streaming                                       | 2.7.0              | 
| Chango Streaming Tx                                    | 2.7.0              | 
| Chango Spark Thrift Server                             | 2.7.0              | 
| ITM(Spark Thrift Server for Iceberg Table Maintenance) | 2.7.0              | 
| Chango Spark SQL Runner                                | 2.7.0              | 
| Chango Data API                                        | 2.7.0              | 
| Chango Trino Gateway                                   | 2.7.0              | 
| Chango Authorizer                                      | 2.7.0              | 
| Chango REST Catalog                                    | 2.7.0              |
| Chango Query Exec                                      | 2.7.0              |
| Chango MCP Server                                      | 2.7.0              |

## Component Ports

### Azkaban
- 28081: Azkaban Web Server
- 28082: Azkaban Executor Server

### Kafka
- 9092: Kafka Server

### Schema Registry
- 8081: Registry Server

### MySQL
- 3306: MySQL Server

### Ozone
- 9862: OM RPC
- 9872: OM Ratis
- 9874: OM HTTP
- 9875: OM HTTPS
- 9861: SCM Data Node
- 9863: SCM Block Client
- 9860: SCM Client
- 9876: SCM HTTP
- 9877: SCM HTTPS
- 9894: SCM Ratis
- 9895: SCM GRPC
- 9961: SCM Security Service
- 9882: Data Node HTTP
- 9883: Data Node HTTPS
- 9858: Container Ratis IPC
- 9859: Container IPC
- 9864: Data Node Client
- 9855: Container Ratis Data Stream
- 9857: Container Ratis Admin
- 9856: Container Ratis Server
- 9878: S3G HTTP
- 9879: S3G HTTPS
- 9891: Recon RPC
- 9888: Recon HTTP
- 9889: Recon HTTPS
- 9884: Freon HTTP
- 9885: Freon HTTPS
- 88: KDC Server
- 749: KDC Admin Server
- 80: NGINX

### Spark
- 7777: Master Server
- 7778: Worker Server
- 8880: Master Web UI
- 8881: Worker Web UI
- 18882: History Server

### Livy
- 8998: Server

### Superset
- 38088: Superset Server

### Trino
- 18080: Coordinator 
- 18081: Worker

### Zookeeper
- 2181: Zookeeper Server 
- 2888: Zookeeper Peer Port 
- 3888: Zookeeper Leader Port

### Zookeeper ICC
- 12181: Zookeeper Server
- 12888: Zookeeper Peer Port
- 13888: Zookeeper Leader Port

### PostgreSQL
- 5432: PostgreSQL Server

### OpenSearch
- 9200: HTTP
- 9300: Transport
- 5601: Dashboard

### Chango Admin
- 28095: Admin Server 
- 8080: NGINX

### Chango Admin UI
- 8123: Admin UI Server

### Chango Spark Thrift Server
- 10000: Server

### ITM
- 11000: Server

### Chango Spark SQL Runner
- 29080: Server

### Chango Data API
- 28097: Server 
- 28098: Jetty Server 
- 27072: Management Server 
- 80: NGINX

### Chango Trino Gateway
- 28096: Server 
- 27081: Management Server 
- 27788: Jetty Proxy Server 
- 6379: Redis Master
- 6380: Redis Slave
- 16379: Redis Master Cluster
- 16380: Redis Slave Cluster
- 443: NGINX SSL

### Chango Authorizer
- 28196: Server 
- 27181: Management Server 
- 81: NGINX

### Chango REST Catalog
- 28197: Server 
- 27182: Management Server 
- 28297: Jetty Proxy Server 
- 8008: NGINX

### Chango Query Exec
- 28291: Server
- 27291: Management Server
- 8009: NGINX

### Chango MCP Server
- 28088: Server
- 27088: Management Server
- 443: NGINX


