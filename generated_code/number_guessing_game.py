import random
import time
import sys

class NumberGuesserGame:
    def __init__(self):
        self.scores = {}
        
    def clear_screen(self):
        print("
" * 2)
        
    def display_banner(self):
        print("=" * 60)
        print("		THE ULTIMATE NUMBER GUESSING GAME")
        print("=" * 60)
        print("Can you crack the code? Test your intuition and logic!
")

    def select_difficulty(self):
        print("Select Difficulty Level:")
        print("1. Easy (1 - 50, 10 attempts)")
        print("2. Medium (1 - 100, 7 attempts)")
        print("3. Hard (1 - 500, 10 attempts)")
        print("4. Custom Range")
        
        while True:
            try:
                choice = int(input("Enter your choice (1-4): "))
                if choice == 1:
                    return 1, 50, 10
                elif choice == 2:
                    return 1, 100, 7
                elif choice == 3:
                    return 1, 500, 10
                elif choice == 4:
                    low = int(input("Enter lower bound: "))
                    high = int(input("Enter upper bound: "))
                    if low >= high:
                        print("Lower bound must be less than upper bound. Try again.")
                        continue
                    attempts = int(input("Enter number of attempts allowed: "))
                    return low, high, attempts
                else:
                    print("Invalid choice. Please select between 1 and 4.")
            except ValueError:
                print("Invalid input. Please enter numbers only.")

    def play_round(self):
        low, high, max_attempts = self.select_difficulty()
        secret_number = random.randint(low, high)
        attempts_left = max_attempts
        guesses = []
        
        print(f"
I have selected a number between {low} and {high}.")
        print(f"You have {max_attempts} attempts to guess it. Good luck!
")
        
        start_time = time.time()
        
        while attempts_left > 0:
            print(f"Attempts remaining: {attempts_left}")
            if guesses:
                print(f"Your previous guesses: {', '.join(map(str, guesses))}")
                
            try:
                guess = int(input(f"Make a guess ({low}-{high}): "))
            except ValueError:
                print("Please enter a valid integer.
")
                continue
                
            if guess < low or guess > high:
                print(f"Out of bounds! Your guess must be between {low} and {high}.
")
                continue
                
            if guess in guesses:
                print("You already tried that number! Try a different one.
")
                continue
                
            guesses.append(guess)
            attempts_left -= 1
            
            if guess == secret_number:
                end_time = time.time()
                elapsed_time = round(end_time - start_time, 2)
                print("
" + "*" * 50)
                print(f"🎉 CONGRATULATIONS! You found the secret number {secret_number}!")
                print(f"⏱️ Time taken: {elapsed_time} seconds")
                print(f"🎯 Attempts used: {len(guesses)}/{max_attempts}")
                print("*" * 50 + "
")
                return True, len(guesses)
            elif guess < secret_number:
                print("📉 Too low! Aim higher.
")
            else:
                print("📈 Too high! Aim lower.
")
                
            # Provide a hint on the last attempt
            if attempts_left == 1 and max_attempts > 2:
                divisible_by_2 = "even" if secret_number % 2 == 0 else "odd"
                print(f"💡 HINT: The secret number is an {divisible_by_2} number.
")
                
        print("
" + "!" * 50)
        print(f"❌ GAME OVER! You ran out of attempts.")
        print(f"🔑 The secret number was: {secret_number}")
        print("!" * 50 + "
")
        return False, max_attempts

    def run(self):
        self.display_banner()
        while True:
            self.play_round()
            play_again = input("Would you like to play again? (y/n): ").strip().lower()
            if play_again != 'y':
                print("
Thanks for playing! Goodbye!")
                break
            self.clear_screen()
            self.display_banner()

if __name__ == "__main__":
    try:
        game = NumberGuesserGame()
        game.run()
    except KeyboardInterrupt:
        print("
Game interrupted. Exiting safely. Goodbye!")
        sys.exit(0)