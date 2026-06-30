{{/*
Expand the name of the chart.
*/}}
{{- define "btcd.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "btcd.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "btcd.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "btcd.labels" -}}
helm.sh/chart: {{ include "btcd.chart" . }}
{{ include "btcd.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "btcd.selectorLabels" -}}
app.kubernetes.io/name: {{ include "btcd.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Map chain name to btcd config file flag
*/}}
{{- define "btcd.chainFlag" -}}
{{- if eq .Values.global.chain "regtest" -}}
simnet=1
{{- else if eq .Values.global.chain "signet" -}}
signet=1
{{- else if eq .Values.global.chain "testnet" -}}
testnet=1
{{- else -}}
{{/* mainnet: no flag needed */}}
{{- end -}}
{{- end -}}
