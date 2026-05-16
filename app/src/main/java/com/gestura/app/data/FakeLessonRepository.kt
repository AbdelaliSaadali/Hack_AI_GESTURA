package com.gestura.app.data

object FakeLessonRepository {

    fun getLessons(): List<Lesson> = listOf(
        Lesson(
            id = "basic_greetings",
            title = "Basic Greetings",
            description = "Start with hello, good morning, and simple polite greetings.",
            difficulty = LessonDifficulty.Beginner,
            unlocked = true,
            tag = "Starter",
            signs = listOf(
                LessonSign("greet_1", "Hello", "Wave your hand gently.", "Hello - open palm wave"),
                LessonSign("greet_2", "Good Morning", "Lift hand from chin outward.", "Good Morning - chin to outward"),
                LessonSign("greet_3", "Good Night", "Tap chin then close hand.", "Good Night - chin tap"),
                LessonSign("greet_4", "Thank You", "Touch chin and move forward.", "Thank You - chin forward"),
                LessonSign("greet_5", "Please", "Circular motion on chest.", "Please - chest circle"),
            ),
        ),
        Lesson(
            id = "introductions",
            title = "Introductions",
            description = "Learn signs for introducing yourself and asking names.",
            difficulty = LessonDifficulty.Beginner,
            unlocked = true,
            signs = listOf(
                LessonSign("intro_1", "My Name Is", "Point to yourself then sign name.", "My Name Is"),
                LessonSign("intro_2", "What", "Index finger wiggle side to side.", "What"),
                LessonSign("intro_3", "Your", "Point forward respectfully.", "Your"),
                LessonSign("intro_4", "Nice To Meet You", "Two index fingers meet.", "Nice To Meet You"),
            ),
        ),
        Lesson(
            id = "daily_expressions",
            title = "Daily Expressions",
            description = "Common expressions for daily communication.",
            difficulty = LessonDifficulty.Intermediate,
            unlocked = true,
            signs = listOf(
                LessonSign("daily_1", "How Are You", "Both hands forward with palms up.", "How Are You"),
                LessonSign("daily_2", "I Am Fine", "Thumb up and nod.", "I Am Fine"),
                LessonSign("daily_3", "See You Later", "Point eyes then outward.", "See You Later"),
                LessonSign("daily_4", "Sorry", "Fist circles over chest.", "Sorry"),
            ),
        ),
        Lesson(
            id = "food_drinks",
            title = "Food & Drinks",
            description = "Essential signs for meals, drinks, and ordering food.",
            difficulty = LessonDifficulty.Intermediate,
            unlocked = true,
            signs = listOf(
                LessonSign("food_1", "Eat", "Bring fingers to mouth.", "Eat"),
                LessonSign("food_2", "Drink", "Mime drinking from cup.", "Drink"),
                LessonSign("food_3", "Water", "W-handshape taps chin.", "Water"),
                LessonSign("food_4", "Coffee", "Stir with index over palm.", "Coffee"),
                LessonSign("food_5", "Hungry", "C-hand slides down chest.", "Hungry"),
            ),
        ),
        Lesson(
            id = "family",
            title = "Family",
            description = "Talk about your family members confidently.",
            difficulty = LessonDifficulty.Intermediate,
            unlocked = false,
            signs = listOf(
                LessonSign("family_1", "Family", "F-hands circle in front.", "Family"),
                LessonSign("family_2", "Mother", "Thumb at chin.", "Mother"),
                LessonSign("family_3", "Father", "Thumb at forehead.", "Father"),
                LessonSign("family_4", "Brother", "L-shapes meet.", "Brother"),
            ),
        ),
        Lesson(
            id = "emergency_phrases",
            title = "Emergency Phrases",
            description = "Critical signs for urgent situations.",
            difficulty = LessonDifficulty.Advanced,
            unlocked = false,
            tag = "Important",
            signs = listOf(
                LessonSign("em_1", "Help", "Thumb-up hand on palm then lift.", "Help"),
                LessonSign("em_2", "Call", "Phone handshape near ear.", "Call"),
                LessonSign("em_3", "Hospital", "H-hand crosses arm.", "Hospital"),
                LessonSign("em_4", "Danger", "Both hands shake outward.", "Danger"),
            ),
        ),
    )
}

