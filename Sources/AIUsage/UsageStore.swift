import Foundation
import Combine

/// Loads usage-summary.json and triggers the Python scraper on a bounded timer.
@MainActor
final class UsageStore: ObservableObject {
    static let refreshIntervalChangedNotification = Notification.Name("io.github.agentusage.refreshIntervalChanged")

    @Published var summary: UsageSummary?
    @Published var sessions: [SessionRecord] = []
    @Published var topSessions: [SessionRecord] = []
    @Published var lastRefresh: Date?
    @Published var isRefreshing = false
    @Published var isLoadingSessions = false
    @Published var errorMessage: String?
    @Published var isMissingSummary = false
    @Published var firstRun = false

    private var timer: Timer?
    private var observer: NSObjectProtocol?
    private var hasStarted = false
    private var sessionsLoaded = false
    private var topSessionsLoaded = false
    private var isLoadingTopSessions = false
    private let jsonURL: URL
    private let scriptURL: URL

    /// Points to ~/Library/Application Support/ai-usage-dashboard/usage-summary.json
    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let folder = appSupport.appendingPathComponent("ai-usage-dashboard")
        jsonURL = folder.appendingPathComponent("usage-summary.json")
        scriptURL = folder.appendingPathComponent("generate_usage_dashboard.py")
    }

    deinit {
        if let observer {
            NotificationCenter.default.removeObserver(observer)
        }
        timer?.invalidate()
    }

    func start() {
        guard !hasStarted else { return }
        hasStarted = true

        observer = NotificationCenter.default.addObserver(
            forName: Self.refreshIntervalChangedNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.restartTimer()
            }
        }

        firstRun = !UserDefaults.standard.bool(forKey: "hasLaunchedBefore")
        if firstRun {
            UserDefaults.standard.set(true, forKey: "hasLaunchedBefore")
        }

        loadSummary()
        restartTimer()
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    func refresh() {
        guard !isRefreshing else { return }
        isRefreshing = true
        errorMessage = nil
        isMissingSummary = false

        let scriptURL = scriptURL
        let jsonURL = jsonURL
        Task { [weak self, scriptURL, jsonURL] in
            let (scrapeResult, summaryResult) = await Task.detached(priority: .utility) {
                let scrapeResult = Self.runScraper(scriptURL: scriptURL, workingDirectory: jsonURL.deletingLastPathComponent())
                let summaryResult: SummaryLoadResult? = if case .success = scrapeResult {
                    Self.decodeSummary(from: jsonURL)
                } else {
                    nil
                }
                return (scrapeResult, summaryResult)
            }.value

            guard let self else { return }
            switch scrapeResult {
            case .success:
                if let summaryResult {
                    self.applySummaryResult(summaryResult, keepLoadedSessionsFresh: true)
                }
            case .failure(let message):
                self.errorMessage = message
            }
            self.isRefreshing = false
        }
    }

    func loadSessionsIfNeeded() {
        guard !sessionsLoaded, !isLoadingSessions else { return }
        isLoadingSessions = true
        errorMessage = nil

        let jsonURL = jsonURL
        Task { [weak self, jsonURL] in
            let result = await Task.detached(priority: .userInitiated) {
                Self.decodeSessions(from: jsonURL)
            }.value

            guard let self else { return }
            switch result {
            case .success(let sessions):
                self.sessions = sessions
                self.topSessions = Self.topSessions(from: sessions)
                self.sessionsLoaded = true
                self.topSessionsLoaded = true
            case .missing:
                self.sessions = []
                self.topSessions = []
                self.sessionsLoaded = false
                self.topSessionsLoaded = false
                self.isMissingSummary = true
            case .failure(let message):
                self.errorMessage = message
            }
            self.isLoadingSessions = false
        }
    }

    func loadTopSessionsIfNeeded() {
        guard !topSessionsLoaded, !isLoadingTopSessions else { return }
        if sessionsLoaded {
            topSessions = Self.topSessions(from: sessions)
            topSessionsLoaded = true
            return
        }

        isLoadingTopSessions = true
        let jsonURL = jsonURL
        Task { [weak self, jsonURL] in
            let result = await Task.detached(priority: .utility) {
                Self.decodeSessions(from: jsonURL)
            }.value

            guard let self else { return }
            switch result {
            case .success(let sessions):
                self.topSessions = Self.topSessions(from: sessions)
                self.topSessionsLoaded = true
            case .missing:
                self.topSessions = []
                self.topSessionsLoaded = false
                self.isMissingSummary = true
            case .failure(let message):
                self.errorMessage = message
            }
            self.isLoadingTopSessions = false
        }
    }

    private func loadSummary() {
        let jsonURL = jsonURL
        Task { [weak self, jsonURL] in
            let result = await Task.detached(priority: .userInitiated) {
                Self.decodeSummary(from: jsonURL)
            }.value

            self?.applySummaryResult(result, keepLoadedSessionsFresh: false)
        }
    }

    private func applySummaryResult(_ result: SummaryLoadResult, keepLoadedSessionsFresh: Bool) {
        switch result {
        case .success(let summary):
            self.summary = summary
            self.lastRefresh = Date()
            self.isMissingSummary = false
            self.errorMessage = nil

            let shouldReloadSessions = keepLoadedSessionsFresh && sessionsLoaded
            let shouldReloadTopSessions = keepLoadedSessionsFresh && topSessionsLoaded
            sessions = []
            topSessions = []
            sessionsLoaded = false
            topSessionsLoaded = false
            if shouldReloadSessions {
                loadSessionsIfNeeded()
            } else if shouldReloadTopSessions {
                loadTopSessionsIfNeeded()
            }
        case .missing:
            self.summary = nil
            self.sessions = []
            self.topSessions = []
            self.sessionsLoaded = false
            self.topSessionsLoaded = false
            self.isMissingSummary = true
            self.errorMessage = nil
        case .failure(let message):
            self.errorMessage = message
        }
    }

    private func restartTimer() {
        timer?.invalidate()
        let interval = autoRefreshSeconds
        let newTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.refresh()
            }
        }
        newTimer.tolerance = min(interval * 0.1, 60)
        timer = newTimer
    }

    private var autoRefreshSeconds: TimeInterval {
        let minutes = UserDefaults.standard.integer(forKey: "autoRefreshMinutes")
        return TimeInterval(max(minutes == 0 ? 60 : minutes, 1) * 60)
    }
}

private enum SummaryLoadResult {
    case success(UsageSummary)
    case missing
    case failure(String)
}

private enum SessionsLoadResult {
    case success([SessionRecord])
    case missing
    case failure(String)
}

private enum ScraperResult {
    case success
    case failure(String)
}

private struct SummaryPayload: Decodable {
    let summary: UsageSummary
}

private struct SessionsPayload: Decodable {
    let sessions: [SessionRecord]
}

private extension UsageStore {
    nonisolated static func decodeSummary(from url: URL) -> SummaryLoadResult {
        guard FileManager.default.fileExists(atPath: url.path) else { return .missing }
        do {
            let data = try Data(contentsOf: url, options: [.mappedIfSafe])
            let payload = try JSONDecoder().decode(SummaryPayload.self, from: data)
            return .success(payload.summary)
        } catch {
            return .failure("Decode error: \(error)")
        }
    }

    nonisolated static func decodeSessions(from url: URL) -> SessionsLoadResult {
        guard FileManager.default.fileExists(atPath: url.path) else { return .missing }
        do {
            let data = try Data(contentsOf: url, options: [.mappedIfSafe])
            let payload = try JSONDecoder().decode(SessionsPayload.self, from: data)
            return .success(payload.sessions)
        } catch {
            return .failure("Sessions decode error: \(error)")
        }
    }

    nonisolated static func topSessions(from sessions: [SessionRecord]) -> [SessionRecord] {
        var top: [SessionRecord] = []
        top.reserveCapacity(5)

        for session in sessions where session.totalTokens > 0 {
            top.append(session)
            top.sort { $0.totalTokens > $1.totalTokens }
            if top.count > 5 {
                top.removeLast()
            }
        }

        return top
    }

    nonisolated static func runScraper(scriptURL: URL, workingDirectory: URL) -> ScraperResult {
        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            return .failure("Python scraper not found at \(scriptURL.path).")
        }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        task.arguments = ["python3", scriptURL.path]
        task.currentDirectoryURL = workingDirectory

        let stderrURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aiusage-scraper-\(UUID().uuidString).log")
        FileManager.default.createFile(atPath: stderrURL.path, contents: nil)

        var stdoutHandle: FileHandle?
        var stderrHandle: FileHandle?
        do {
            stdoutHandle = try FileHandle(forWritingTo: URL(fileURLWithPath: "/dev/null"))
            stderrHandle = try FileHandle(forWritingTo: stderrURL)
            task.standardOutput = stdoutHandle
            task.standardError = stderrHandle

            try task.run()
            task.waitUntilExit()

            try? stdoutHandle?.close()
            try? stderrHandle?.close()

            if task.terminationStatus == 0 {
                try? FileManager.default.removeItem(at: stderrURL)
                return .success
            }

            let stderr = (try? String(contentsOf: stderrURL, encoding: .utf8)) ?? ""
            try? FileManager.default.removeItem(at: stderrURL)
            let trimmed = stderr.trimmingCharacters(in: .whitespacesAndNewlines)
            let suffix = trimmed.isEmpty ? "" : ": \(String(trimmed.prefix(4_000)))"
            return .failure("Python exit \(task.terminationStatus)\(suffix)")
        } catch {
            try? stdoutHandle?.close()
            try? stderrHandle?.close()
            try? FileManager.default.removeItem(at: stderrURL)
            return .failure(error.localizedDescription)
        }
    }
}
