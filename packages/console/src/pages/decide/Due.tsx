/**
 * The decisions due for review (`decisions.reviews.due`), each a link to its
 * entry, where the review is made.
 */
import { decisionsReviewsDue } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useRead } from '../../api';
import { displayDate } from '../../kit/dates';
import { Empty, Loaded } from '../../kit/layout';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { journalPath } from './LabNav';

const l = labStrings;

export function DueReviews() {
  const locale = useLocale();
  const query = useRead('decisions.reviews.due', decisionsReviewsDue);
  return (
    <Loaded query={query}>
      {({ reviews }) =>
        reviews.length ? (
          <ul className="list">
            {reviews.map((review) => (
              <li key={review.id} className="dated">
                <span className="dated-date">{displayDate(review.review_on, locale)}</span>
                <span>
                  <Link to={journalPath(review.id)} aria-label={l.reviewIt(review.question)}>
                    {review.question}
                  </Link>{' '}
                  <span className="muted">· {l.chose(review.chosen)}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>{l.noneDue}</Empty>
        )
      }
    </Loaded>
  );
}

