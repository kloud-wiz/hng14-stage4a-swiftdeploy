package swiftdeploy.infrastructure

import future.keywords.if
import future.keywords.contains

# Default deny
default allow := false

# Allow only if no violations exist
allow if count(violations) == 0

# Collect all violations
violations contains msg if {
    input.disk_free_gb < data.infrastructure.min_disk_free_gb
    msg := sprintf("Disk free (%.1fGB) is below minimum threshold (%.1fGB)", [input.disk_free_gb, data.infrastructure.min_disk_free_gb])
}

violations contains msg if {
    input.cpu_load > data.infrastructure.max_cpu_load
    msg := sprintf("CPU load (%.2f) exceeds maximum threshold (%.2f)", [input.cpu_load, data.infrastructure.max_cpu_load])
}

violations contains msg if {
    input.memory_percent > data.infrastructure.max_memory_percent
    msg := sprintf("Memory usage (%.1f%%) exceeds maximum threshold (%.1f%%)", [input.memory_percent, data.infrastructure.max_memory_percent])
}
