window.googleLogin = async () => {
    try {
        const provider = new GoogleAuthProvider();

        const result = await signInWithPopup(
            auth,
            provider
        );

        console.log("Email:", result.user.email);

        const token =
            await result.user.getIdToken();

        console.log("Token:", token);

    } catch (error) {

        console.log("ERROR CODE:", error.code);
        console.log("ERROR MESSAGE:", error.message);

        alert(
            error.code + "\n" + error.message
        );
    }
};