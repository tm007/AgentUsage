import Foundation

/// Mirrors usage-summary.json exactly for Decodable
struct UsageSummary: Codable {
    let generatedAt: String
    let tools: [ToolSummary]
    let projects: [ProjectSummary]
    let days: [DayMetrics]
    let models: [ModelSummary]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case tools, projects, days, models
    }
}

struct ToolSummary: Codable, Identifiable {
    var id: String { tool }
    let tool: String
    let sessions, projects, activeDays: Int
    let inputTokens, outputTokens, totalTokens, exactTokenSessions: Int
    let cacheCreationTokens, cacheReadTokens: Int
    let activityProxy: Double
    let costProxy: Double
    let readOps, writeOps, filesModified, linesAdded, linesRemoved: Int

    enum CodingKeys: String, CodingKey {
        case tool, sessions, projects
        case activeDays = "active_days"
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
        case totalTokens = "total_tokens"
        case exactTokenSessions = "exact_token_sessions"
        case cacheCreationTokens = "cache_creation_tokens"
        case cacheReadTokens = "cache_read_tokens"
        case activityProxy = "activity_proxy"
        case costProxy = "cost_proxy"
        case readOps = "read_ops"
        case writeOps = "write_ops"
        case filesModified = "files_modified"
        case linesAdded = "lines_added"
        case linesRemoved = "lines_removed"
    }
}

struct ProjectSummary: Codable, Identifiable {
    var id: String { "\(tool)-\(project)" }
    let tool, project, projectPath: String
    let sessions: Int
    let totalTokens: Int
    let activityProxy: Double
    let durationMinutes, filesModified, linesAdded, linesRemoved: Int
    let confidence: String

    enum CodingKeys: String, CodingKey {
        case tool, project
        case projectPath = "project_path"
        case sessions
        case totalTokens = "total_tokens"
        case activityProxy = "activity_proxy"
        case durationMinutes = "duration_minutes"
        case filesModified = "files_modified"
        case linesAdded = "lines_added"
        case linesRemoved = "lines_removed"
        case confidence
    }
}

struct DayMetrics: Codable {
    let day: String
    let claude, codex, openCode, cursor, hermes, pi: Double?

    enum CodingKeys: String, CodingKey {
        case day
        case claude = "Claude"
        case codex = "Codex"
        case openCode = "OpenCode"
        case cursor = "Cursor"
        case hermes = "Hermes"
        case pi = "Pi"
    }

    var total: Double {
        let c = claude ?? 0
        let x = codex ?? 0
        let o = openCode ?? 0
        let r = cursor ?? 0
        let h = hermes ?? 0
        let p = pi ?? 0
        return c + x + o + r + h + p
    }
}

struct ModelSummary: Codable, Identifiable {
    var id: String { "\(tool)-\(model)" }
    let tool, model: String
    let sessions: Int
}

struct RootPayload: Codable {
    let summary: UsageSummary
    let sessions: [SessionRecord]
}

struct SessionRecord: Codable, Identifiable {
    var id: String { sessionId }
    let tool, sessionId, projectPath, projectLabel: String
    let startTime, endTime, day, model: String
    let inputTokens, outputTokens, cacheCreationTokens, cacheReadTokens, totalTokens: Int
    let exactTokens: Bool
    let activityProxy: Double
    let costProxy: Double
    let filesModified, linesAdded, linesRemoved, readOps, writeOps, durationMinutes, messageCount: Int
    let confidence, dataNotes: String

    enum CodingKeys: String, CodingKey {
        case tool, sessionId = "session_id", projectPath = "project_path"
        case projectLabel = "project_label"
        case startTime = "start_time", endTime = "end_time", day, model
        case inputTokens = "input_tokens", outputTokens = "output_tokens"
        case cacheCreationTokens = "cache_creation_tokens"
        case cacheReadTokens = "cache_read_tokens"
        case totalTokens = "total_tokens"
        case exactTokens = "exact_tokens"
        case activityProxy = "activity_proxy"
        case costProxy = "cost_proxy"
        case filesModified = "files_modified"
        case linesAdded = "lines_added"
        case linesRemoved = "lines_removed"
        case readOps = "read_ops", writeOps = "write_ops"
        case durationMinutes = "duration_minutes"
        case messageCount = "message_count"
        case confidence, dataNotes = "data_notes"
    }
}
