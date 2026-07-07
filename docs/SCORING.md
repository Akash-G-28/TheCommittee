# Committee Accuracy Methodology

Committee accuracy is a personal feedback signal, not an objective measure of whether a life
decision was correct.

Only outcomes marked `RESOLVED` are scored. Pending and follow-up-due decisions remain excluded.
The final post-rebuttal vote and confidence are used; if an agent did not revise, its first-round
vote is used.

For outcomes with satisfaction at least 6/10 and regret at most 4/10, a vote matching the user's
actual choice scores 1, an opposing vote scores 0, and `MAYBE` scores 0.5. When satisfaction is at
most 4 or regret is at least 6, matching is reversed because the chosen action produced a poor
reported outcome. Mixed outcomes score every position 0.5 rather than manufacturing certainty.

Accuracy is the mean score per agent and decision category. Confidence calibration groups final
opinions into 20-percentage-point buckets and compares mean confidence with mean score. Small
samples must be shown with their counts and should not be interpreted as stable performance.

Limitations include self-reported hindsight, changing circumstances, ambiguous causal attribution,
and selection bias in which outcomes users choose to resolve. Scores should help reflection and
calibration; they must not rank agents as universally correct or make consequential decisions for
the user.

