import SwiftUI

struct AboutView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(alignment: .center, spacing: 16) {
                ZStack {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [.cyan.opacity(0.95), .pink.opacity(0.75)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 72, height: 72)

                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.system(size: 34, weight: .bold))
                        .foregroundStyle(.white)
                }

                VStack(alignment: .leading, spacing: 5) {
                    Text("AgentUsage")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text("Local-first AI usage analytics for macOS")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                }
            }

            Text("AgentUsage turns local usage traces from supported AI coding tools into a private dashboard for tokens, cache, model mix, source coverage, daily volume, top projects, and largest sessions.")
                .font(.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Divider()

            VStack(alignment: .leading, spacing: 12) {
                InfoRow(icon: "lock.shield", title: "Local by default", detail: "Runs on your Mac and writes reports under Application Support. Generated usage reports are intentionally excluded from git.")
                InfoRow(icon: "eye.slash", title: "Prompt-safe reports", detail: "Raw prompts and message content are not written to the generated dashboard files.")
                InfoRow(icon: "shippingbox", title: "Public-safe source", detail: "The collector defaults to public-safe output that avoids embedding full local project paths in aggregate report rows.")
            }

            Divider()

            VStack(alignment: .leading, spacing: 6) {
                Text("Supported sources")
                    .font(.subheadline.weight(.semibold))
                Text("Claude, Codex, Cursor, OpenCode, Hermes, and Pi")
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 0)
        }
        .padding(28)
        .frame(width: 620, height: 460)
    }
}

private struct InfoRow: View {
    let icon: String
    let title: String
    let detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(.cyan)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(detail)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
