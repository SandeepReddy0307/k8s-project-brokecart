{{- define "brokecart.kafka.validate" -}}
{{- $replicas := int .Values.replicaCount -}}
{{- if or (lt $replicas 3) (eq (mod $replicas 2) 0) -}}
{{- fail "Combined KRaft mode requires an odd replicaCount of at least 3" -}}
{{- end -}}
{{- if or (lt (int .Values.topics.replicationFactor) 1) (gt (int .Values.topics.replicationFactor) $replicas) -}}
{{- fail "topics.replicationFactor must be between 1 and replicaCount" -}}
{{- end -}}
{{- if or (lt (int .Values.topics.minInSyncReplicas) 1) (gt (int .Values.topics.minInSyncReplicas) (int .Values.topics.replicationFactor)) -}}
{{- fail "topics.minInSyncReplicas must be between 1 and topics.replicationFactor" -}}
{{- end -}}
{{- if lt (int .Values.topics.partitions) 1 -}}
{{- fail "topics.partitions must be positive" -}}
{{- end -}}
{{- if not (regexMatch "^[A-Za-z0-9_-]{22}$" .Values.kraft.clusterId) -}}
{{- fail "kraft.clusterId must be a 22-character Kafka UUID; keep it stable across restarts" -}}
{{- end -}}
{{- if and .Values.pdb.enabled (ge (int .Values.pdb.minAvailable) $replicas) -}}
{{- fail "pdb.minAvailable must be lower than replicaCount to allow maintenance" -}}
{{- end -}}
{{- range $service, $permissions := .Values.acls.services -}}
{{- if not (has $service $.Values.auth.clients) -}}
{{- fail (printf "ACL service %s is missing from auth.clients" $service) -}}
{{- end -}}
{{- range concat $permissions.produces $permissions.consumes -}}
{{- if not (has . $.Values.topics.names) -}}
{{- fail (printf "ACL for %s references undeclared topic %s" $service .) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- if and .Values.acls.ui.enabled (not (has "kafka-ui" .Values.auth.clients)) -}}
{{- fail "Kafka UI requires kafka-ui in auth.clients" -}}
{{- end -}}
{{- end -}}
