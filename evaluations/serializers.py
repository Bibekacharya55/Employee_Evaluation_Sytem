from rest_framework import serializers

from accounts.models import User
from questions.models import Category
from .models import Answer, Evaluation, EvaluationCycle, PeerAssignment


class EvaluationCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationCycle
        fields = [
            "id",
            "name",
            "status",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]


class PeerAssignmentSerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(read_only=True)
    evaluator_id = serializers.IntegerField(read_only=True)
    evaluatee_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PeerAssignment
        fields = [
            "id",
            "cycle_id",
            "evaluator_id",
            "evaluatee_id",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "cycle_id",
            "evaluator_id",
            "evaluatee_id",
            "status",
            "created_at",
            "updated_at",
        ]

class PeerAssignmentCreateSerializer(serializers.Serializer):
    cycle_id = serializers.IntegerField()
    evaluatee_id = serializers.IntegerField()

    def validate_cycle_id(self, value):
        if not EvaluationCycle.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Evaluation cycle not found.")
        return value

    def validate(self, attrs):
        evaluator = self.context["request"].user
        evaluatee_id = attrs["evaluatee_id"]
        cycle_id = attrs["cycle_id"]

        if evaluator.id == evaluatee_id:
            raise serializers.ValidationError("You cannot assign yourself as a peer evaluatee.")

        if not User.objects.filter(pk=evaluatee_id, is_active=True).exists():
            raise serializers.ValidationError({"evaluatee_id": "Employee not found."})

        if PeerAssignment.objects.filter(
            cycle_id=cycle_id,
            evaluator=evaluator,
            evaluatee_id=evaluatee_id,
        ).exists():
            raise serializers.ValidationError("This peer assignment already exists.")

        if PeerAssignment.objects.filter(
        cycle_id=cycle_id,
        evaluator_id=evaluatee_id,
        evaluatee=evaluator,
    ).exists():
             raise serializers.ValidationError(
            "Reciprocal peer assignments are not allowed."
        )


        return attrs

    def create(self, validated_data):
        return PeerAssignment.objects.create(
            cycle_id=validated_data["cycle_id"],
            evaluator=self.context["request"].user,
            evaluatee_id=validated_data["evaluatee_id"],
            status=PeerAssignment.STATUS_PENDING,
        )


class AvailableEmployeeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    availability = serializers.CharField()


class AnswerSerializer(serializers.ModelSerializer):
    evaluation_id = serializers.IntegerField(read_only=True)
    question_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Answer
        fields = [
            "id",
            "evaluation_id",
            "question_id",
            "score",
            "justification",
            "created_at",
            "updated_at",
        ]


class DraftAnswerItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(required=False)
    question = serializers.IntegerField(required=False)
    score = serializers.IntegerField(min_value=1, max_value=5)
    justification = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        q_id = attrs.get("question_id") or attrs.get("question")
        if not q_id:
            raise serializers.ValidationError("Either question or question_id is required.")
        attrs["question_id"] = q_id
        return attrs


class SaveAnswersSerializer(serializers.Serializer):
    answers = DraftAnswerItemSerializer(many=True)


class EvaluationSerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(read_only=True)
    evaluator_id = serializers.IntegerField(read_only=True)
    evaluatee_id = serializers.IntegerField(read_only=True)
    peer_assignment_id = serializers.IntegerField(read_only=True, allow_null=True)
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            "id",
            "cycle_id",
            "evaluator_id",
            "evaluatee_id",
            "peer_assignment_id",
            "evaluation_type",
            "status",
            "submitted_at",
            "created_at",
            "updated_at",
            "answers",
        ]


class EvaluationDetailAnswerSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source="question.id")

    class Meta:
        model = Answer
        fields = [
            "id",
            "question_id",
            "score",
            "justification",
            "created_at",
            "updated_at",
        ]


class EvaluationDetailSerializer(EvaluationSerializer):
    categories = serializers.SerializerMethodField()

    class Meta(EvaluationSerializer.Meta):
        fields = EvaluationSerializer.Meta.fields + ["categories"]

    def get_categories(self, evaluation):
        answers_by_question = {
            answer.question_id: answer for answer in evaluation.answers.all()
        }

        categories = []
        for category in Category.objects.prefetch_related("questions").all():
            questions = []
            for question in category.questions.all():
                answer = answers_by_question.get(question.id)
                if answer:
                    answer_data = EvaluationDetailAnswerSerializer(answer).data
                else:
                    answer_data = {
                        "id": None,
                        "question_id": question.id,
                        "score": None,
                        "justification": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                questions.append(
                    {
                        "id": question.id,
                        "text": question.text,
                        "answer": answer_data,
                    }
                )

            categories.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "questions": questions,
                }
            )

        return categories


class EvaluationCreateSerializer(serializers.Serializer):
    cycle_id = serializers.IntegerField(required=False)
    cycle = serializers.IntegerField(required=False)
    evaluation_type = serializers.ChoiceField(
        choices=Evaluation.TYPE_CHOICES,
        required=False,
        default=Evaluation.TYPE_SELF,
    )
    peer_assignment_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        c_id = attrs.get("cycle_id") or attrs.get("cycle")
        if not c_id:
            active_cycle = EvaluationCycle.objects.filter(status=EvaluationCycle.STATUS_OPEN).first()
            if not active_cycle:
                raise serializers.ValidationError({"cycle_id": "No active evaluation cycle found."})
            c_id = active_cycle.id
        else:
            if not EvaluationCycle.objects.filter(pk=c_id).exists():
                raise serializers.ValidationError({"cycle_id": "Evaluation cycle not found."})

        attrs["cycle_id"] = c_id
        evaluation_type = attrs.get("evaluation_type", Evaluation.TYPE_SELF)
        attrs["evaluation_type"] = evaluation_type

        evaluator = self.context["request"].user
        peer_assignment_id = attrs.get("peer_assignment_id")

        if evaluation_type == Evaluation.TYPE_PEER:
            if not peer_assignment_id:
                raise serializers.ValidationError(
                    {"peer_assignment_id": "This field is required for peer evaluations."}
                )

            try:
                peer_assignment = PeerAssignment.objects.get(pk=peer_assignment_id)
            except PeerAssignment.DoesNotExist:
                raise serializers.ValidationError(
                    {"peer_assignment_id": "Peer assignment not found."}
                )

            if peer_assignment.evaluator_id != evaluator.id:
                raise serializers.ValidationError(
                    {"peer_assignment_id": "You are not the evaluator for this peer assignment."}
                )

            if peer_assignment.cycle_id != c_id:
                raise serializers.ValidationError(
                    {"peer_assignment_id": "Peer assignment does not belong to this cycle."}
                )

            attrs["peer_assignment"] = peer_assignment
            attrs["evaluatee"] = peer_assignment.evaluatee
        else:
            attrs["peer_assignment"] = None
            attrs["evaluatee"] = evaluator

        return attrs

    def create(self, validated_data):
        return Evaluation.objects.create(
            cycle_id=validated_data["cycle_id"],
            evaluator=self.context["request"].user,
            evaluatee=validated_data["evaluatee"],
            peer_assignment=validated_data.get("peer_assignment"),
            evaluation_type=validated_data["evaluation_type"],
            status=Evaluation.STATUS_DRAFT,
        )
