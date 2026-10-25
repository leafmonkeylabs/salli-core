// Salli's widgets (design 15). Words come with the snapshot, from the app's
// catalogue; the only ones here are the gallery's and "Open Salli", for a
// widget placed before the app has written anything.
import SwiftUI
import WidgetKit

@main
struct SalliWidgets: WidgetBundle {
  init() { _ = Fonts.registered }

  var body: some Widget {
    SafeWidget()
    WaitingWidget()
    ForecastWidget()
    SpentWidget()
    NetWorthWidget()
    ComingUpWidget()
    PaydayWidget()
  }
}

struct SafeWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "safe", provider: GlanceProvider()) { entry in
      SafeView(entry: entry)
    }
    .configurationDisplayName("Safe to spend")
    .description("What you can spend until your next income.")
    .supportedFamilies([.systemSmall, .accessoryRectangular])
  }
}

struct WaitingWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "waiting", provider: GlanceProvider()) { entry in
      WaitingView(entry: entry)
    }
    .configurationDisplayName("Waiting")
    .description("Decisions to review, reminders due, statements to review.")
    .supportedFamilies([.systemSmall, .accessoryRectangular])
  }
}

private let openSalli = "Open Salli"

struct SafeView: View {
  let entry: GlanceEntry
  @Environment(\.widgetFamily) private var family
  @Environment(\.colorScheme) private var scheme

  var body: some View {
    let glance = entry.glance
    let look = Look(glance, scheme)
    Group {
      if family == .accessoryRectangular {
        VStack(alignment: .leading, spacing: 0) {
          Text(glance?.safe.label ?? openSalli).font(.caption).widgetAccentable()
          if let glance, !entry.old {
            // Privacy mode: the lock screen is seen by anyone holding the
            // phone, so the amount stays masked there; the app shows it.
            Text(verbatim: "••••").font(.headline).accessibilityHidden(true)
            Text(glance.safe.until).font(.caption)
          } else if let glance {
            Text(glance.open).font(.caption)
          }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
      } else {
        VStack(alignment: .leading, spacing: 4) {
          Mark(colour: look.accent).frame(width: 20, height: 14).accessibilityHidden(true)
          Spacer(minLength: 0)
          if let glance, !entry.old {
            Text(glance.safe.label).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
            Text(figure(glance))
              .privacySensitive()
              .font(.custom("Geist-Medium", size: 22))
              .foregroundStyle(look.ink)
              .minimumScaleFactor(0.6)
              .lineLimit(1)
              .accessibilityLabel(glance.safe.spoken)
            Text(glance.safe.until).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
          } else {
            Text(glance?.safe.label ?? openSalli).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
            if let glance { Text(glance.open).font(.custom("Geist-Medium", size: 15)).foregroundStyle(look.ink) }
          }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
      }
    }
    .containerBackground(for: .widget) { look.paper }
  }

  private func figure(_ glance: Glance) -> String {
    glance.safe.currency.isEmpty ? glance.safe.figure : "\(glance.safe.currency) \(glance.safe.figure)"
  }
}

struct WaitingView: View {
  let entry: GlanceEntry
  @Environment(\.widgetFamily) private var family
  @Environment(\.colorScheme) private var scheme

  var body: some View {
    let glance = entry.glance
    let look = Look(glance, scheme)
    // Two lines fit, and then how many more.
    let lines = glance.map { Array($0.waiting.lines.prefix(2)) } ?? []
    Group {
      if family == .accessoryRectangular {
        VStack(alignment: .leading, spacing: 0) {
          Text(glance?.waiting.label ?? openSalli).font(.headline).widgetAccentable()
          if let glance, !entry.old {
            ForEach(lines, id: \.self) { Text($0).font(.caption) }
            if !glance.waiting.more.isEmpty { Text(glance.waiting.more).font(.caption) }
          } else if let glance {
            Text(glance.open).font(.caption)
          }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
      } else {
        VStack(alignment: .leading, spacing: 0) {
          Text(glance?.waiting.label ?? openSalli)
            .font(.custom("Geist-Regular", size: 13))
            .foregroundStyle(look.muted)
            .padding(.bottom, 8)
          if let glance, !entry.old {
            ForEach(lines, id: \.self) { line in
              Rectangle().fill(look.rule).frame(height: 1)
              Text(line)
                .font(.custom("Geist-Regular", size: 14))
                .foregroundStyle(look.ink)
                .lineLimit(2)
                .padding(.vertical, 6)
            }
            if !glance.waiting.more.isEmpty {
              Text(glance.waiting.more).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
            }
          } else if let glance {
            Text(glance.open).font(.custom("Geist-Medium", size: 15)).foregroundStyle(look.ink)
          }
          Spacer(minLength: 0)
          if let glance {
            Text(glance.host)
              .font(.custom("GeistMono-Regular", size: 11))
              .foregroundStyle(look.muted)
              .lineLimit(1)
              .truncationMode(.middle)
          }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
      }
    }
    .containerBackground(for: .widget) { look.paper }
  }
}

/** The brand's mark: the logo's four bars (docs/brand/assets), in ledger green. */
struct Mark: View {
  var colour: Color = Color("mark")
  var body: some View {
    GeometryReader { box in
      // The bars as the logo draws them, in its 114.86 × 80.4 box.
      let bars: [(CGFloat, CGFloat, CGFloat)] = [(0, 0, 74.66), (84.71, 0, 30.15), (0, 51.69, 30.15), (40.2, 51.69, 74.66)]
      let sx = box.size.width / 114.86
      let sy = box.size.height / 80.4
      ZStack(alignment: .topLeading) {
        ForEach(0..<bars.count, id: \.self) { i in
          Rectangle()
            .fill(colour)
            .frame(width: bars[i].2 * sx, height: 28.71 * sy)
            .offset(x: bars[i].0 * sx, y: bars[i].1 * sy)
        }
      }
    }
  }
}
