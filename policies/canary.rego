package swiftdeploy.canary

import future.keywords.if
import future.keywords.contains

# Default deny
default allow := false

# Allow only if no violations exist
allow if count(violations) == 0

# Collect all violations
violations contains msg if {
    input.error_rate > data.canary.max_error_rate
    msg := sprintf("Error rate (%.2f%%) exceeds maximum threshold (%.2f%%)", [input.error_rate * 100, data.canary.max_error_rate * 100])
}

violations contains msg if {
    input.p99_latency_ms > data.canary.max_p99_latency_ms
    msg := sprintf("P99 latency (%.1fms) exceeds maximum threshold (%.1fms)", [input.p99_latency_ms, data.canary.max_p99_latency_ms])
}
