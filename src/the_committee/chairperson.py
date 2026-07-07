"""Deterministic synthesis of committee opinions."""

from collections import Counter

from the_committee.domain import AgentOpinion, Decision, RevisedOpinion, Verdict, Vote


class Chairperson:
    def synthesize(
        self,
        decision: Decision,
        opinions: list[AgentOpinion],
        revised_opinions: list[RevisedOpinion] | None = None,
    ) -> Verdict:
        if not opinions:
            raise ValueError("At least one opinion is required")

        revisions = {item.agent: item for item in revised_opinions or []}
        final_votes = [
            revisions[item.agent].vote if item.agent in revisions else item.vote
            for item in opinions
        ]
        counts = Counter(final_votes)
        highest = max(counts.values())
        leaders = [vote for vote, count in counts.items() if count == highest]
        vote = leaders[0] if len(leaders) == 1 else Vote.MAYBE
        confidences = [
            revisions[item.agent].confidence if item.agent in revisions else item.confidence
            for item in opinions
            if (revisions[item.agent].vote if item.agent in revisions else item.vote) == vote
        ]
        if not confidences:
            confidences = [item.confidence for item in opinions]
        mean_confidence = sum(confidences) / len(confidences)
        consensus = highest / len(opinions)
        confidence = round(mean_confidence * (0.7 + 0.3 * consensus), 2)
        deciding_opinion = max(opinions, key=lambda item: (item.confidence, item.agent.value))
        dissenters = [
            opinion
            for opinion in opinions
            if (revisions[opinion.agent].vote if opinion.agent in revisions else opinion.vote)
            != vote
        ]
        minority = None
        if dissenters:
            strongest = max(dissenters, key=lambda item: (item.confidence, item.agent.value))
            final_vote = (
                revisions[strongest.agent].vote
                if strongest.agent in revisions
                else strongest.vote
            )
            minority = f"{strongest.agent.value} voted {final_vote}: {strongest.summary}"

        return Verdict(
            decision_id=decision.id,
            vote=vote,
            confidence=confidence,
            summary=f"The committee recommends {vote} ({highest} of {len(opinions)} votes).",
            deciding_factor=deciding_opinion.key_factors[0],
            minority_report=minority,
        )
