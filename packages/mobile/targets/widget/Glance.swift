// The snapshot the app writes (src/lib/glance.ts, version 2), and the
// timeline that shows it: as written, then from a day after its newest read,
// a request to open the app instead of figures that may be wrong.
import CoreText
import Foundation
import SwiftUI
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
  struct Forecast: Decodable {
    let label: String
    let low: String
    let spoken: String
    let points: [Double]
    let lowIndex: Int
  }
  struct Spent: Decodable {
    let label: String
    let figure: String
    let then: String
    let spoken: String
  }
  struct NetWorth: Decodable {
    let label: String
    let figure: String
    let spoken: String
    let points: [Double]
  }
  struct ComingUp: Decodable {
    struct Row: Decodable {
      let day: String
      let title: String
      let amount: String
      let `in`: Bool
    }
    let label: String
    let rows: [Row]
    let spoken: String
  }
  struct Payday: Decodable {
    let days: Int
    let unit: String
    let share: Double
    let spoken: String
  }
  struct Palette: Decodable {
    let paper: String
    let ink: String
    let muted: String
    let rule: String
    let accent: String
    let tile: String
    let tileText: String
  }
  struct Colors: Decodable {
    let light: Palette
    let dark: Palette
  }
  let v: Int
  let at: Double
  let host: String
  let safe: Safe
  let waiting: Waiting
  let forecast: Forecast?
  let spent: Spent?
  let netWorth: NetWorth?
  let comingUp: ComingUp?
  let payday: Payday?
  let colors: Colors
  let open: String

  static func read() -> Glance? {
    guard let text = UserDefaults(suiteName: appGroup)?.string(forKey: "glance"),
          let glance = try? JSONDecoder().decode(Glance.self, from: Data(text.utf8)),
          glance.v == 2
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

/** The app's theme for a widget: the snapshot's colours on the side the phone shows, else the brand's. */
struct Look {
  let paper: Color
  let ink: Color
  let muted: Color
  let rule: Color
  let accent: Color
  let tile: Color
  let tileText: Color

  init(_ glance: Glance?, _ scheme: ColorScheme) {
    guard let colors = glance?.colors else {
      paper = Color("paper"); ink = Color("ink"); muted = Color("muted"); rule = Color("rule")
      accent = Color("mark"); tile = Color("mark"); tileText = Color("paper")
      return
    }
    let p = scheme == .dark ? colors.dark : colors.light
    paper = Color(css: p.paper); ink = Color(css: p.ink); muted = Color(css: p.muted); rule = Color(css: p.rule)
    accent = Color(css: p.accent); tile = Color(css: p.tile); tileText = Color(css: p.tileText)
  }
}

extension Color {
  /** A colour as the app's theme writes it: #RRGGBB or rgba(r, g, b, a). */
  init(css: String) {
    let text = css.trimmingCharacters(in: .whitespaces)
    if text.hasPrefix("#"), text.count == 7, let n = UInt32(text.dropFirst(), radix: 16) {
      self.init(red: Double((n >> 16) & 0xFF) / 255, green: Double((n >> 8) & 0xFF) / 255, blue: Double(n & 0xFF) / 255)
      return
    }
    if text.hasPrefix("rgba(") || text.hasPrefix("rgb(") {
      let inside = text.drop(while: { $0 != "(" }).dropFirst().prefix(while: { $0 != ")" })
      let parts = inside.split(separator: ",").map { Double($0.trimmingCharacters(in: .whitespaces)) ?? 0 }
      if parts.count >= 3 {
        self.init(.sRGB, red: parts[0] / 255, green: parts[1] / 255, blue: parts[2] / 255, opacity: parts.count > 3 ? parts[3] : 1)
        return
      }
    }
    self.init(white: 0.5)
  }
}
