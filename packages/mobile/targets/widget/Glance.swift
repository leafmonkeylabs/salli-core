// The snapshot the app writes (src/lib/glance.ts, version 1), and the
// timeline that shows it: as written, then from a day after its newest read,
// a request to open the app instead of figures that may be wrong.
import CoreText
import Foundation
import WidgetKit

let appGroup = "group.money.salli.app"

struct Glance: Decodable {
  struct Safe: Decodable {
    let label: String
    let figure: String
    let currency: String
    let spoken: String
    let until: String
  }
  struct Waiting: Decodable {
    let label: String
    let lines: [String]
    let more: String
  }
  let v: Int
  let at: Double
  let host: String
  let safe: Safe
  let waiting: Waiting
  let open: String

  static func read() -> Glance? {
    guard let text = UserDefaults(suiteName: appGroup)?.string(forKey: "glance"),
          let glance = try? JSONDecoder().decode(Glance.self, from: Data(text.utf8)),
          glance.v == 1
    else { return nil }
    return glance
  }

  /** When its figures stop being shown: a day after the newest read. */
  var oldAfter: Date { Date(timeIntervalSince1970: at / 1000).addingTimeInterval(24 * 60 * 60) }
}

struct GlanceEntry: TimelineEntry {
  let date: Date
  let glance: Glance?
  /** Too old to show, or nothing written yet: the widget asks to open the app. */
  let old: Bool
}

struct GlanceProvider: TimelineProvider {
  func placeholder(in context: Context) -> GlanceEntry {
    GlanceEntry(date: Date(), glance: nil, old: true)
  }

  func getSnapshot(in context: Context, completion: @escaping (GlanceEntry) -> Void) {
    let glance = Glance.read()
    completion(GlanceEntry(date: Date(), glance: glance, old: glance.map { $0.oldAfter <= Date() } ?? true))
  }

  // The app reloads the timeline whenever it writes; nothing here asks a server.
  func getTimeline(in context: Context, completion: @escaping (Timeline<GlanceEntry>) -> Void) {
    let now = Date()
    guard let glance = Glance.read() else {
      completion(Timeline(entries: [GlanceEntry(date: now, glance: nil, old: true)], policy: .never))
      return
    }
    var entries = [GlanceEntry(date: now, glance: glance, old: glance.oldAfter <= now)]
    if glance.oldAfter > now { entries.append(GlanceEntry(date: glance.oldAfter, glance: glance, old: true)) }
    completion(Timeline(entries: entries, policy: .never))
  }
}

/** Geist, from the target's own copy (assets/fonts), registered once for the extension. */
enum Fonts {
  static let registered: Void = {
    for name in ["Geist_400Regular", "Geist_500Medium", "GeistMono_400Regular"] {
      if let url = Bundle.main.url(forResource: name, withExtension: "ttf", subdirectory: "fonts")
        ?? Bundle.main.url(forResource: name, withExtension: "ttf") {
        CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
      }
    }
  }()
}
