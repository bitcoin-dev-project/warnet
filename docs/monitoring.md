# Monitoring

## Monitoring container resource usage

When run in docker, a few additional containers are started up:

* CAdvisor (container Monitoring)
* Prometheus (log scraper)
* Grafana (graphing/dashboard tool)

## CAdvisor

CAdvisor needs no additional setup, and can be accessed from the docker host at
localhost:8080

## Prometheus

Prometheus should also not need any additional setup, and can be accessed from
the docker host at localhost:9090

## Grafana

Grafana is provisioned with a single default dashboard, but alternative
dashboards can be added or created.

Grafana can be accessed on the docker host from localhost:3000 using username
`admin` and password `admin` by default.

The default dashboard is called "Docker Container & Host Metrics" and can be
accessed via the "dashboards" tab, or from the bottom right of the home screen.

Additional dashboards and datasources may be added in the future.
