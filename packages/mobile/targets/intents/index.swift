// "Draft from a bank's message", for Shortcuts and its automations ("When I get
// a message from EXAMPLEBANK"). It queues the message on this phone, in the
// app group, for Salli's own rules to read the next time it runs
// (src/inbox.tsx); it sends nothing and decides nothing itself.
import AppIntents
import Foundation

@main
struct SalliIntentsExtension: AppIntentsExtension {}

struct DraftFromMessage: AppIntent {
  static var title: LocalizedStringResource = "Draft from a bank’s message"
  static var description = IntentDescription(
    "Salli reads the message with your rules on this phone and drafts what they read for review. A message no rule watches is dropped; nothing is posted until you approve it."
  )
  static var openAppWhenRun = false

  @Parameter(title: "Message")
  var message: String

  @Parameter(title: "From", description: "Who sent it, as your automation names them.")
  var sender: String?

  static var parameterSummary: some ParameterSummary {
    Summary("Draft \(\.$message) from \(\.$sender)")
  }

  func perform() async throws -> some IntentResult & ProvidesDialog {
    Inbox.add(text: message, sender: sender ?? "")
    return .result(dialog: "Salli will read it.")
  }
}

struct SalliShortcuts: AppShortcutsProvider {
  static var appShortcuts: [AppShortcut] {
    AppShortcut(
      intent: DraftFromMessage(),
      phrases: ["Draft a bank message in \(.applicationName)"],
      shortTitle: "Draft from a message",
      systemImageName: "text.bubble"
    )
  }
}

/// The queue in the app group, as src/lib/inbox.ts reads it: a JSON array of
/// {id, text, sender, at}. At most 200 wait; past that the oldest go.
enum Inbox {
  static let group = "group.money.salli.app"
  static let key = "inbox"

  static func add(text: String, sender: String) {
    guard let defaults = UserDefaults(suiteName: group) else { return }
    var queue: [[String: String]] = []
    if let stored = defaults.string(forKey: key),
       let parsed = try? JSONSerialization.jsonObject(with: Data(stored.utf8)) as? [[String: String]] {
      queue = parsed
    }
    queue.append([
      "id": UUID().uuidString,
      "text": text,
      "sender": sender,
      "at": ISO8601DateFormatter().string(from: Date()),
    ])
    let kept = Array(queue.suffix(200))
    if let data = try? JSONSerialization.data(withJSONObject: kept), let json = String(data: data, encoding: .utf8) {
      defaults.set(json, forKey: key)
    }
  }
}
