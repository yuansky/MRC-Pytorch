import json
import torch
from torch.utils.data import (DataLoader, RandomSampler, TensorDataset)


class RaceExample(object):
    """A single training/test example for the RACE dataset."""
    '''
    For RACE dataset:
    race_id: data id
    context_sentence: article
    start_ending: question
    ending_0/1/2/3: option_0/1/2/3
    label: true answer
    '''

    def __init__(self,
                 race_id,
                 context_sentence,
                 start_ending,
                 ending_0,
                 ending_1,
                 ending_2,
                 ending_3,
                 label=None):
        self.race_id = race_id
        self.context_sentence = context_sentence
        self.start_ending = start_ending
        self.endings = [
            ending_0,
            ending_1,
            ending_2,
            ending_3,
        ]
        self.label = label

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        l = [
            f"id: {self.race_id}",
            f"article: {self.context_sentence}",
            f"question: {self.start_ending}",
            f"option_0: {self.endings[0]}",
            f"option_1: {self.endings[1]}",
            f"option_2: {self.endings[2]}",
            f"option_3: {self.endings[3]}",
        ]

        if self.label is not None:
            l.append(f"label: {self.label}")

        return ", ".join(l)


class InputFeatures(object):
    def __init__(self,
                 example_id,
                 choices_features,
                 label

                 ):
        self.example_id = example_id
        self.choices_features = [
            {
                'input_ids': input_ids,
                'input_mask': input_mask,
                'segment_ids': segment_ids
            }
            for _, input_ids, input_mask, segment_ids in choices_features
        ]
        self.label = label


def convert_examples_to_features(examples, tokenizer, max_seq_length):
    """Loads a data file into a list of `InputBatch`s."""

    # RACE is a multiple choice task. To perform this task using Bert,
    # we will use the formatting proposed in "Improving Language
    # Understanding by Generative Pre-Training" and suggested by
    # @jacobdevlin-google in this issue
    # https://github.com/google-research/bert/issues/38.
    #
    # The input will be like:
    # [CLS] Article [SEP] Question + Option [SEP]
    # for each option
    #
    # The model will output a single value for each input. To get the
    # final decision of the model, we will run a softmax over these 4
    # outputs.
    features = []
    for example_index, example in enumerate(examples):
        context_tokens = tokenizer.tokenize(example.context_sentence)
        start_ending_tokens = tokenizer.tokenize(example.start_ending)

        choices_features = []
        for ending_index, ending in enumerate(example.endings):
            # We create a copy of the context tokens in order to be
            # able to shrink it according to ending_tokens
            context_tokens_choice = context_tokens[:]
            ending_tokens = start_ending_tokens + tokenizer.tokenize(ending)
            # Modifies `context_tokens_choice` and `ending_tokens` in
            # place so that the total length is less than the
            # specified length.  Account for [CLS], [SEP], [SEP] with
            # "- 3"
            _truncate_seq_pair(context_tokens_choice,
                               ending_tokens, max_seq_length - 3)

            tokens = ["[CLS]"] + context_tokens_choice + \
                ["[SEP]"] + ending_tokens + ["[SEP]"]
            segment_ids = [0] * (len(context_tokens_choice) + 2) + \
                [1] * (len(ending_tokens) + 1)

            input_ids = tokenizer.convert_tokens_to_ids(tokens)
            input_mask = [1] * len(input_ids)

            # Zero-pad up to the sequence length.
            padding = [0] * (max_seq_length - len(input_ids))
            input_ids += padding
            input_mask += padding
            segment_ids += padding

            assert len(input_ids) == max_seq_length
            assert len(input_mask) == max_seq_length
            assert len(segment_ids) == max_seq_length

            choices_features.append(
                (tokens, input_ids, input_mask, segment_ids))

        label = example.label

        features.append(
            InputFeatures(
                example_id=example.race_id,
                choices_features=choices_features,
                label=label
            )
        )

    return features


def _truncate_seq_pair(tokens_a, tokens_b, max_length):
    """Truncates a sequence pair in place to the maximum length."""

    # This is a simple heuristic which will always truncate the longer sequence
    # one token at a time. This makes more sense than truncating an equal percent
    # of tokens from each, since if one sequence is very short then each token
    # that's truncated likely contains more information than a longer sequence.
    while True:
        total_length = len(tokens_a) + len(tokens_b)
        if total_length <= max_length:
            break
        if len(tokens_a) > len(tokens_b):
            tokens_a.pop()
        else:
            tokens_b.pop()


def select_field(features, field):
    return [
        [
            choice[field]
            for choice in feature.choices_features
        ]
        for feature in features
    ]

def convert_features_to_tensors(features, batch_size):
    all_input_ids = torch.tensor(
        select_field(features, 'input_ids'), dtype=torch.long)
    all_input_mask = torch.tensor(
        select_field(features, 'input_mask'), dtype=torch.long)
    all_segment_ids = torch.tensor(
        select_field(features, 'segment_ids'), dtype=torch.long)
    all_label_ids = torch.tensor(
        [f.label for f in features], dtype=torch.long)

    data = TensorDataset(all_input_ids, all_input_mask,
                         all_segment_ids, all_label_ids)

    sampler = RandomSampler(data)
    dataloader = DataLoader(data, sampler=sampler, batch_size=batch_size)

    return dataloader

def read_race_examples(filename):

    examples = []

    with open(filename, 'r') as f:
        dataes = json.load(f)
        for data in dataes:
            examples.append(
                RaceExample(
                    race_id = data['race_id'],
                    context_sentence = data['article'],
                    start_ending = data['question'],
                    ending_0 = data['option_0'],
                    ending_1 = data['option_1'],
                    ending_2 = data['option_2'],
                    ending_3 = data['option_3'],
                    label = data['label']
                 )
            )
    
    return examples


def load_data(filename, tokenizer, max_seq_length, batch_size):

    examples = read_race_examples(filename)
    features = convert_examples_to_features(examples, tokenizer, max_seq_length)
    dataloader = convert_features_to_tensors(features, batch_size)
    return dataloader, len(examples)



if __name__ == "__main__":
    from pytorch_pretrained_bert.tokenization import BertTokenizer

    tokenizer = BertTokenizer.from_pretrained(
        "/home/songyingxin/datasets/pytorch-bert/vocabs/bert-base-uncased-vocab.txt", do_lower_case=True)

    filename = "/home/songyingxin/datasets/RACE/all/test.json"

    load_data(filename, tokenizer, 120, 32)

    print(1)