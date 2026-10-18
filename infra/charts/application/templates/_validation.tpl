{{- if .Values.deployment.enabled -}}
{{- if .Values.autoscaling.enabled -}}
{{- if or (lt (int .Values.autoscaling.minReplicas) 1) (lt (int .Values.autoscaling.maxReplicas) (int .Values.autoscaling.minReplicas)) -}}
{{- fail "autoscaling requires 1 <= minReplicas <= maxReplicas" -}}
{{- end -}}
{{- if le (int .Values.autoscaling.targetCPUUtilizationPercentage) 0 -}}
{{- fail "autoscaling CPU target must be positive" -}}
{{- end -}}
{{- end -}}
{{- if and .Values.vpa.enabled (ne .Values.vpa.updateMode "Off") -}}
{{- fail "VPA is recommendation-only; vpa.updateMode must be Off" -}}
{{- end -}}
{{- if eq (get .Values.config "SPRING_PROFILES_ACTIVE") "local" -}}
{{- fail "The local development profile must not be deployed to the cluster" -}}
{{- end -}}
{{- end -}}
