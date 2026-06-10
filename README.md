# Preprocessing the text

## Step 0: Preparing the Text Manually
Before we proceed with the program's analysis of the text, it will be very helpful to prepare the text in advance.
Add top-level headings in the format `### [Section Name]` to make it easier for the program to locate specific sections later on.
- [x] Step 0 Ready

## Step 1: Text analysis only
We read the file and check:
- where the headers are,
- what the sections look like,
- where one rule ends and another begins.
- [x] Step 1 Ready

## Step 2: Dividing into blocks
At this stage, we don’t create “perfect chunks” yet.
We just cut out logical pieces.
- [x] Step 2 Ready

## Stage 3: Adding metadata
Each block gets a description:
- where it comes from,
- what type of content it is,
- what it’s called.
- [x] Step 3 Ready

## Stage 4: Chunking only after that
We combine or split blocks so that they are suitable for semantic search.
To start with, I’d set a target of roughly:
- 200–400 tokens per chunk,
- with a small overlap, e.g., 30–60 tokens.
- [x] Step 4 Ready

## Stage 5: Manual review and correction of the chunks
After the program has done its work, we review the chunks manually.
We check if they are coherent, if the metadata is correct, and if they are suitable for semantic search.
We check also a minimum, maximum numbr of tokens in the chunk.
- [x] Step 5 Ready


# Tests

## Test 1: "What is Reanimation Protocols?"
- [x] Test 1 Ready

__Test 1 Passed__

## Test 2: "Describe me a Awakened Dynasty?"
- [x] Test 2 Ready

__Test 2 Failed__

## Test 3: "What is the Nether-realm Casket and what does it do?"
- [x] Test 3 Ready

__Test 3 Passed__

## Test 4: "What does do Command Protocols?"
- [x] Test 4 Ready

__Test 4 Passed__

## Test 5: "Which stratagems can I use during the shooting phase in the Canoptek Court detachment?"
- [x] Test 5 Ready

__Test 5 50% correct__