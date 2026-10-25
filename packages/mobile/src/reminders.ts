/**
 * Marking a reminder done, as Home and Attention both do: the row leaves at
 * once (its list's exit motion), with a light tap and VoiceOver saying so,
 * and comes back if the server refuses.
 */
import { remindersMarkDone, type Reminder, type ReminderList } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { AccessibilityInfo } from 'react-native';
import { useApi } from './api';
import { strings } from './strings';

export function useMarkDone() {
  const api = useApi();
  const queryClient = useQueryClient();
  const lists = { queryKey: [api.server, 'reminders.list'] };
  return useMutation({
    mutationFn: (reminder: Reminder) => api.call(remindersMarkDone, { path: { reminder_id: reminder.id } }),
    onMutate: async (reminder) => {
      await queryClient.cancelQueries(lists);
      const before = queryClient.getQueriesData<ReminderList>(lists);
      queryClient.setQueriesData<ReminderList>(lists, (data) => data && { ...data, reminders: data.reminders.map((r) => (r.id === reminder.id ? { ...r, status: 'done' } : r)) });
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      AccessibilityInfo.announceForAccessibility(strings.attention.doneSaid(reminder.kind));
      return { before };
    },
    onError: (_error, reminder, context) => {
      for (const [key, data] of context?.before ?? []) queryClient.setQueryData(key, data);
      AccessibilityInfo.announceForAccessibility(strings.attention.doneRefused(reminder.kind));
    },
    onSettled: () => Promise.all([queryClient.invalidateQueries(lists), queryClient.invalidateQueries({ queryKey: [api.server, 'insights.signals'] })]),
  });
}
