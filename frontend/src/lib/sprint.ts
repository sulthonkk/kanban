export type SprintStatus = "Normal" | "Warning" | "Urgent" | "Completed";

const quotes = ["Progress beats perfection.", "Build one step at a time.", "Consistency compounds.", "Done is better than perfect.", "Small improvements create big momentum.", "Every task finished creates momentum.", "Great products are built one iteration at a time.", "Focus on progress, not pressure.", "Clarity comes through action.", "Stay consistent.", "Make the next useful move.", "Momentum grows through action."];

function localDate(value: string) { return new Date(`${value}T00:00:00`); }
function startOfToday(today: Date) { return new Date(today.getFullYear(), today.getMonth(), today.getDate()); }

export function dailyQuote(date: Date) {
  const firstDay = new Date(date.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((date.getTime() - firstDay.getTime()) / 86_400_000);
  return quotes[(dayOfYear - 1) % quotes.length];
}

export function formatDate(date: Date) {
  return new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" }).format(date);
}

export function getSprintMetrics(startValue: string, deadlineValue: string, now = new Date()) {
  const start = localDate(startValue);
  const deadline = localDate(deadlineValue);
  const today = startOfToday(now);
  const totalDays = Math.max(1, Math.round((deadline.getTime() - start.getTime()) / 86_400_000));
  const daysFromStart = Math.round((today.getTime() - start.getTime()) / 86_400_000);
  const daysRemaining = Math.max(0, Math.round((deadline.getTime() - today.getTime()) / 86_400_000));
  const beforeStart = today < start;
  const completed = today > deadline;
  const currentDay = beforeStart ? 0 : completed ? totalDays : Math.min(totalDays, daysFromStart + 1);
  const progress = beforeStart ? 0 : completed ? 100 : Math.round((currentDay / totalDays) * 100);
  const status: SprintStatus = completed ? "Completed" : daysRemaining === 0 ? "Urgent" : daysRemaining <= 3 ? "Warning" : "Normal";
  return { totalDays, currentDay, progress, daysRemaining, status, beforeStart, completed };
}
