{{- define "mychart.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mychart.fullname" -}}
{{- printf "%s-%s" (include "mychart.name" .) .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
