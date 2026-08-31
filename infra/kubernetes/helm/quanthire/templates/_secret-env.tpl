{{/*
Inject env vars from pre-created Kubernetes Secrets (see values*.yaml secrets section).
Each entry maps secretKeyRef name/key to an env var of the same name.
*/}}
{{- define "quanthire.azureSecretEnv" -}}
{{- range $group, $secret := .Values.secrets }}
{{- range $secret.keys }}
- name: {{ . }}
  valueFrom:
    secretKeyRef:
      name: {{ $secret.name }}
      key: {{ . }}
{{- end }}
{{- end }}
{{- end }}
