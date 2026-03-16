-- Create Library Curriculum Data for Testing
-- Run this on staging database to populate library content

-- First, let's update one existing curriculum to be a library_master for testing
-- (Replace with actual curriculum ID from your database)
UPDATE curriculums
SET source_type = 'library_master',
    title = '[LIBRARY] ' || title,
    description = 'Official YouSpeak Library Content - ' || COALESCE(description, '')
WHERE source_type = 'teacher_upload'
LIMIT 2;

-- Or create new library curriculums from scratch:

-- French Beginner Curriculum
INSERT INTO curriculums (
    id,
    school_id,
    title,
    description,
    language_id,
    source_type,
    status,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '1738bd06-2b9d-4e72-9737-42c2e39a75f1',  -- Replace with actual school_id
    'French for Beginners - A1 Level',
    'Official YouSpeak library curriculum for absolute beginners in French. Master basic greetings, numbers 1-100, and everyday conversations.',
    1,  -- Assuming 1 is French language_id
    'library_master',
    'published',
    NOW(),
    NOW()
);

-- Spanish Beginner Curriculum
INSERT INTO curriculums (
    id,
    school_id,
    title,
    description,
    language_id,
    source_type,
    status,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '1738bd06-2b9d-4e72-9737-42c2e39a75f1',  -- Replace with actual school_id
    'Spanish for Beginners - A1 Level',
    'Official YouSpeak library curriculum. Learn Spanish basics including greetings, introductions, and common phrases.',
    2,  -- Assuming 2 is Spanish language_id (adjust if different)
    'library_master',
    'published',
    NOW(),
    NOW()
);

-- English Advanced Curriculum
INSERT INTO curriculums (
    id,
    school_id,
    title,
    description,
    language_id,
    source_type,
    status,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '1738bd06-2b9d-4e72-9737-42c2e39a75f1',  -- Replace with actual school_id
    'Business English - B2 Level',
    'Official YouSpeak library curriculum for professional English. Focus on business communication, presentations, and negotiations.',
    3,  -- Assuming 3 is English language_id (adjust if different)
    'library_master',
    'published',
    NOW(),
    NOW()
);

-- French Intermediate Curriculum
INSERT INTO curriculums (
    id,
    school_id,
    title,
    description,
    language_id,
    source_type,
    status,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '1738bd06-2b9d-4e72-9737-42c2e39a75f1',  -- Replace with actual school_id
    'French Intermediate - A2 Level',
    'Official YouSpeak library curriculum for intermediate learners. Covers past tense, future planning, and complex conversations.',
    1,
    'library_master',
    'published',
    NOW(),
    NOW()
);

-- German Beginner Curriculum
INSERT INTO curriculums (
    id,
    school_id,
    title,
    description,
    language_id,
    source_type,
    status,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '1738bd06-2b9d-4e72-9737-42c2e39a75f1',  -- Replace with actual school_id
    'German for Beginners - A1 Level',
    'Official YouSpeak library curriculum. Learn German alphabet, basic grammar, and essential vocabulary for daily life.',
    4,  -- Assuming 4 is German language_id (adjust if different)
    'library_master',
    'published',
    NOW(),
    NOW()
);

-- Verify the data
SELECT
    id,
    title,
    source_type,
    status,
    language_id,
    created_at
FROM curriculums
WHERE source_type = 'library_master'
ORDER BY created_at DESC;
