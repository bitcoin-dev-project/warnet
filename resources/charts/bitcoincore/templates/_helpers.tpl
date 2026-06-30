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
Add network section heading in bitcoin.conf.

Bitcoin Core image tags are not always strict SemVer.

Examples we want to accept:
  10.0          -> 10.0.0
  10.0.0        -> 10.0.0
  10.0.0-rc1    -> 10.0.0-rc.1
  10.0rc1       -> 10.0.0-rc.1
  10.0-rc1      -> 10.0.0-rc.1

Helm's semverCompare requires strict SemVer, so normalize first.
*/}}
{{- define "bitcoincore.check_semver" -}}
{{- $tag := .Values.image.tag | toString -}}
{{- $semver := "" -}}

{{/*
Case: already valid normal SemVer.

Matches:
  10.0.0

Regex:
  ^     start of string
  \d+   major version: one or more digits
  \.    literal dot
  \d+   minor version: one or more digits
  \.    literal dot
  \d+   patch version: one or more digits
  $     end of string
*/}}
{{- if regexMatch `^\d+\.\d+\.\d+$` $tag -}}
  {{- $semver = $tag -}}

{{/*
Case: missing patch version.

Matches:
  10.0

Converts:
  10.0 -> 10.0.0
*/}}
{{- else if regexMatch `^\d+\.\d+$` $tag -}}
  {{- $semver = printf "%s.0" $tag -}}

{{/*
Case: has patch version, but rc prerelease is not strict SemVer.

Matches:
  10.0.0-rc1

Converts:
  10.0.0-rc1 -> 10.0.0-rc.1

Regex:
  ^        start of string
  (\d+)    capture major version
  \.       literal dot
  (\d+)    capture minor version
  \.       literal dot
  (\d+)    capture patch version
  -rc      literal "-rc"
  (\d+)    capture rc number
  $        end of string

Replacement:
  ${1}.${2}.${3}-rc.${4}
*/}}
{{- else if regexMatch `^\d+\.\d+\.\d+-rc\d+$` $tag -}}
  {{- $semver = regexReplaceAll `^(\d+)\.(\d+)\.(\d+)-rc(\d+)$` $tag `${1}.${2}.${3}-rc.${4}` -}}

{{/*
Case: missing patch version and rc is attached directly to minor version.

Matches:
  10.0rc1

Converts:
  10.0rc1 -> 10.0.0-rc.1

Regex:
  ^       start of string
  (\d+)   capture major version
  \.      literal dot
  (\d+)   capture minor version
  rc      literal "rc"
  (\d+)   capture rc number
  $       end of string

Replacement:
  ${1}.${2}.0-rc.${3}
*/}}
{{- else if regexMatch `^\d+\.\d+rc\d+$` $tag -}}
  {{- $semver = regexReplaceAll `^(\d+)\.(\d+)rc(\d+)$` $tag `${1}.${2}.0-rc.${3}` -}}

{{/*
Case: missing patch version, with hyphenated rc prerelease.

Matches:
  10.0-rc1

Converts:
  10.0-rc1 -> 10.0.0-rc.1

Regex:
  ^       start of string
  (\d+)   capture major version
  \.      literal dot
  (\d+)   capture minor version
  -rc     literal "-rc"
  (\d+)   capture rc number
  $       end of string

Replacement:
  ${1}.${2}.0-rc.${3}
*/}}
{{- else if regexMatch `^\d+\.\d+-rc\d+$` $tag -}}
  {{- $semver = regexReplaceAll `^(\d+)\.(\d+)-rc(\d+)$` $tag `${1}.${2}.0-rc.${3}` -}}

{{/*
Fallback:
  Leave the tag unchanged.

Note:
  If this is not valid SemVer, semverCompare will fail.
  Add another normalization case above if more tag formats need support.
*/}}
{{- else -}}
  {{- $semver = $tag -}}
{{- end -}}

{{/*
Only add the network section heading for Bitcoin Core versions
where bitcoin.conf supports per-network sections.

Strip pre-release suffix before comparison because Helm's semverCompare
does not match pre-release versions with >= constraints by default.
e.g. "31.1.0-rc.1" would fail ">=0.17.0" without this normalization.
*/}}
{{- $semver_no_prerelease := regexReplaceAll "-.*$" $semver "" -}}
{{- if semverCompare ">=0.17.0" $semver_no_prerelease -}}
[{{ .Values.global.chain }}]
{{- end -}}

{{- end -}}
