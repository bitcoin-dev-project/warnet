{{/*
Expand the name of the chart.
*/}}
{{- define "bitcoincore.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "bitcoincore.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "bitcoincore.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "bitcoincore.labels" -}}
helm.sh/chart: {{ include "bitcoincore.chart" . }}
{{ include "bitcoincore.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "bitcoincore.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bitcoincore.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "bitcoincore.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "bitcoincore.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}


{{/*
Add network section heading in bitcoin.conf after v0.17.0
*/}}
{{- define "bitcoincore.check_semver" -}}
{{- $version := semverCompare ">=0.17.0" .Values.image.tag -}}
{{- if $version -}}
[{{ .Values.chain }}]
{{- end -}}
{{- end -}}
