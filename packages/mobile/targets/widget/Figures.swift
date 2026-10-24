// The figure widgets (design 35): the cash forecast, this month's spending,
// net worth, and the days to the next income. Like the others, they show
// only what the snapshot carries: figures (hidden unless the person allows
// amounts outside the app), never a name from the books.
import SwiftUI
import WidgetKit

private let openSalli = "Open Salli"

struct ForecastWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "forecast", provider: GlanceProvider()) { entry in
      ForecastView(entry: entry)
    }
    .configurationDisplayName("Cash forecast")
    .description("Your cash over the next 60 days, and when it is lowest.")
    .supportedFamilies([.systemMedium])
  }
}

struct SpentWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "spent", provider: GlanceProvider()) { entry in
      SpentView(entry: entry)
    }
    .configurationDisplayName("Spent this month")
    .description("This month so far, beside last month to the same day.")
    .supportedFamilies([.systemSmall])
  }
}

struct NetWorthWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "netWorth", provider: GlanceProvider()) { entry in
      NetWorthView(entry: entry)
    }
    .configurationDisplayName("Net worth")
    .description("Your net worth, with the last 12 months.")
    .supportedFamilies([.systemSmall])
  }
}

struct PaydayWidget: Widget {
  var body: some WidgetConfiguration {
    StaticConfiguration(kind: "payday", provider: GlanceProvider()) { entry in
      PaydayView(entry: entry)
    }
    .configurationDisplayName("Days to income")
    .description("Days until your next income.")
    .supportedFamilies([.accessoryCircular])
  }
}

/** A line through heights from 0 to 1, oldest first; the low point marked when given. */
struct Spark: View {
  let points: [Double]
  let colour: Color
  var low: Int? = nil

  var body: some View {
    GeometryReader { box in
      let w = box.size.width
      let h = box.size.height
      let at = { (i: Int) -> CGPoint in
        CGPoint(
          x: points.count > 1 ? w * CGFloat(i) / CGFloat(points.count - 1) : w / 2,
          y: 3 + (h - 6) * CGFloat(1 - points[i])
        )
      }
      ZStack {
        Path { path in
          guard !points.isEmpty else { return }
          path.move(to: at(0))
          for i in points.indices.dropFirst() { path.addLine(to: at(i)) }
        }
        .stroke(colour, lineWidth: 1.5)
        if let low, points.indices.contains(low) {
          Circle().fill(colour).frame(width: 7, height: 7).position(at(low))
        }
      }
    }
    .accessibilityHidden(true)
  }
}

/** What a figure widget shows when there is nothing to show: its name and a way into the app. */
private struct Empty: View {
  let label: String
  let glance: Glance?
  let look: Look

  var body: some View {
    VStack(alignment: .leading, spacing: 4) {
      Text(label).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
      Spacer(minLength: 0)
      Text(glance?.open ?? openSalli).font(.custom("Geist-Medium", size: 15)).foregroundStyle(look.ink)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
  }
}

struct ForecastView: View {
  let entry: GlanceEntry
  @Environment(\.colorScheme) private var scheme

  var body: some View {
    let look = Look(entry.glance, scheme)
    Group {
      if let glance = entry.glance, let forecast = glance.forecast, !entry.old {
        VStack(alignment: .leading, spacing: 8) {
          HStack(alignment: .firstTextBaseline) {
            Text(forecast.label).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
            Spacer()
            Text(forecast.low).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
          }
          .accessibilityElement(children: .ignore)
          .accessibilityLabel(forecast.spoken)
          Spark(points: forecast.points, colour: look.accent, low: forecast.lowIndex)
        }
      } else {
        Empty(label: "Cash forecast", glance: entry.glance, look: look)
      }
    }
    .containerBackground(for: .widget) { look.paper }
  }
}

struct SpentView: View {
  let entry: GlanceEntry
  @Environment(\.colorScheme) private var scheme

  var body: some View {
    let look = Look(entry.glance, scheme)
    Group {
      if let glance = entry.glance, let spent = glance.spent, !entry.old {
        VStack(alignment: .leading, spacing: 4) {
          Text(spent.label).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
          Spacer(minLength: 0)
          Text(spent.figure)
            .font(.custom("Geist-Medium", size: 24))
            .foregroundStyle(look.ink)
            .minimumScaleFactor(0.6)
            .lineLimit(1)
          if !spent.then.isEmpty {
            Text(spent.then).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
          }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spent.spoken)
      } else {
        Empty(label: "Spent this month", glance: entry.glance, look: look)
      }
    }
    .containerBackground(for: .widget) { look.paper }
  }
}

struct NetWorthView: View {
  let entry: GlanceEntry
  @Environment(\.colorScheme) private var scheme

  var body: some View {
    let look = Look(entry.glance, scheme)
    Group {
      if let glance = entry.glance, let worth = glance.netWorth, !entry.old {
        VStack(alignment: .leading, spacing: 6) {
          Text(worth.label).font(.custom("Geist-Regular", size: 13)).foregroundStyle(look.muted)
          Text(worth.figure)
            .font(.custom("Geist-Medium", size: 24))
            .foregroundStyle(look.ink)
            .minimumScaleFactor(0.6)
            .lineLimit(1)
          Spark(points: worth.points, colour: look.accent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(worth.spoken)
      } else {
        Empty(label: "Net worth", glance: entry.glance, look: look)
      }
    }
    .containerBackground(for: .widget) { look.paper }
  }
}

/** On the lock screen: days to the next income inside a ring that fills as it nears; the system tints it. */
struct PaydayView: View {
  let entry: GlanceEntry

  var body: some View {
    Group {
      if let payday = entry.glance?.payday, !entry.old {
        Gauge(value: payday.share) {
          Text(payday.unit)
        } currentValueLabel: {
          Text("\(payday.days)").font(.system(.title3, design: .rounded).weight(.semibold))
        }
        .gaugeStyle(.accessoryCircularCapacity)
        .widgetAccentable()
        .accessibilityLabel(payday.spoken)
      } else {
        Image(systemName: "calendar").font(.title3).accessibilityLabel(openSalli)
      }
    }
    .containerBackground(for: .widget) { Color.clear }
  }
}
