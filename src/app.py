from datetime import datetime, timedelta, timezone
import jwt
import streamlit as st
from streamlit_navigation_bar import st_navbar
import utils
from streamlit_feedback import streamlit_feedback
import os

UTC = timezone.utc

# Set the page configuration
st.set_page_config(page_title="Luxe Home Renovations Custom Q Chat")

# Init configuration
utils.retrieve_config_from_agent()

pages = ["Chat", "Profile", "About", "Authenticate"]
parent_dir = os.path.dirname(os.path.abspath(__file__))  # Get the parent directory
logo_path = os.path.join(parent_dir, "hammer-svgrepo-com.svg")  # Set the logo path

styles = {
    "nav": {
        "background-color": "rgb(123, 209, 146)",
    },
    "div": {
        "max-width": "32rem",
    },
    "span": {
        "border-radius": "0.5rem",
        "color": "rgb(49, 51, 63)",
        "margin": "0 0.125rem",
        "padding": "0.4375rem 0.625rem",
    },
    "active": {
        "background-color": "rgba(255, 255, 255, 0.25)",
    },
    "hover": {
        "background-color": "rgba(255, 255, 255, 0.35)",
    },
    "img": {  # Added styles for the logo image
        "padding-right": "14px",
    },
}

def navigation_bar():
    page = st_navbar(pages, styles=styles, logo_path=logo_path)  # Added logo_path

    if page == "Chat" or page is None:
        if "token" not in st.session_state:
            # Display content for the homepage before authentication
            st.write("Welcome to Luxe Home Renovations!")
            st.write("Please authenticate to access the chat feature.")
        else:
            home_page()
    elif page == "Profile":
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("Profile Page Content")
    elif page == "About":
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("About Page Content")
    elif page == "Authenticate":
            authenticate()

def authenticate():
    oauth2 = utils.configure_oauth_component()
    if "token" not in st.session_state:
        redirect_uri = f"https://{utils.OAUTH_CONFIG['ExternalDns']}/component/streamlit_oauth.authorize_button/index.html"
        result = oauth2.authorize_button("Authenticate", scope="openid", pkce="S256", redirect_uri=redirect_uri)

        if result and "token" in result:
            st.session_state.token = result.get("token")
            st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(st.session_state.token["id_token"])
            st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(tz=UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
            st.rerun()
    else:
        token = st.session_state["token"]
        refresh_token = token["refresh_token"]
        user_email = jwt.decode(token["id_token"], options={"verify_signature": False})["email"]

        if st.button("Refresh Cognito Token"):
            token = oauth2.refresh_token(token, force=True)
            token["refresh_token"] = refresh_token
            st.session_state.token = token
            st.rerun()

        if "idc_jwt_token" not in st.session_state:
            st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(token["id_token"])
            st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
        elif st.session_state["idc_jwt_token"]["expires_at"] < datetime.now(UTC):
            try:
                st.session_state["idc_jwt_token"] = utils.refresh_iam_oidc_token(st.session_state["idc_jwt_token"]["refreshToken"])
                st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
            except Exception as e:
                st.error(f"Error refreshing Identity Center token: {e}. Please reload the page.")

        st.write("Welcome: ", user_email)

        home_page()

def home_page():

    # Define a function to clear the chat history
    def clear_chat_history():
        st.session_state.messages = [{"role": "assistant", "content": "How may I assist you today?"}]
        st.session_state.questions = []
        st.session_state.answers = []
        st.session_state.input = ""
        st.session_state["chat_history"] = []
        st.session_state["conversationId"] = ""
        st.session_state["parentMessageId"] = ""

    col1, col2 = st.columns([1, 1])

    with col2:
        st.button("Clear Chat History", on_click=clear_chat_history)

    # Initialize the chat messages in the session state if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]

    if "conversationId" not in st.session_state:
        st.session_state["conversationId"] = ""

    if "parentMessageId" not in st.session_state:
        st.session_state["parentMessageId"] = ""

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if "questions" not in st.session_state:
        st.session_state.questions = []

    if "answers" not in st.session_state:
        st.session_state.answers = []

    if "input" not in st.session_state:
        st.session_state.input = ""

    # Display the chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # User-provided prompt
    if prompt := st.chat_input():
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

    # If the last message is from the user, generate a response from the Q_backend
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                placeholder = st.empty()
                response = utils.get_queue_chain(
                    prompt,
                    st.session_state["conversationId"],
                    st.session_state["parentMessageId"],
                    st.session_state["idc_jwt_token"]["idToken"]
                )
                if "references" in response:
                    full_response = f"""{response["answer"]}\n\n---\n{response["references"]}"""
                else:
                    full_response = f"""{response["answer"]}\n\n---\nNo sources"""
                placeholder.markdown(full_response)
                st.session_state["conversationId"] = response["conversationId"]
                st.session_state["parentMessageId"] = response["parentMessageId"]

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        feedback = streamlit_feedback(
            feedback_type="thumbs",
            optional_text_label="[Optional] Please provide an explanation",
        )

def main():
    navigation_bar()

if __name__ == "__main__":
    main()
# from datetime import datetime, timedelta, timezone

# import jwt
# import jwt.algorithms
# import streamlit as st  #all streamlit commands will be available through the "st" alias
# from streamlit_navigation_bar import st_navbar
# import utils
# from streamlit_feedback import streamlit_feedback

# UTC=timezone.utc

# # Init configuration
# utils.retrieve_config_from_agent()

# st.set_page_config(page_title="Luxe Home Renovations Custom Q Chat") #HTML title

# col1, col2, col3 = st.columns([1, 2, 1])
# with col2:
#     st.title("Luxe Home Renovations") #page title

# # Define a function to clear the chat history
# def clear_chat_history():
#     st.session_state.messages = [{"role": "assistant", "content": "How may I assist you today?"}]
#     st.session_state.questions = []
#     st.session_state.answers = []
#     st.session_state.input = ""
#     st.session_state["chat_history"] = []
#     st.session_state["conversationId"] = ""
#     st.session_state["parentMessageId"] = ""

# def navigation_bar():
#     page = st_navbar(["Home", "Profile", "About"])
#     st.write(page)
    
# oauth2 = utils.configure_oauth_component()
# if "token" not in st.session_state:
#     # If not, show authorize button
#     redirect_uri = f"https://{utils.OAUTH_CONFIG['ExternalDns']}/component/streamlit_oauth.authorize_button/index.html"
    
#     result = oauth2.authorize_button("Authenticate",scope="openid", pkce="S256", redirect_uri=redirect_uri)

#     if result and "token" in result:
#         # If authorization successful, save token in session state
#         st.session_state.token = result.get("token")
#         # Retrieve the Identity Center token
#         st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(st.session_state.token["id_token"])
#         st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(tz=UTC) + \
#             timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
#         st.rerun()
# else:
#     token = st.session_state["token"]
#     refresh_token = token["refresh_token"] # saving the long lived refresh_token
#     user_email = jwt.decode(token["id_token"], options={"verify_signature": False})["email"]
#     if st.button("Refresh Cognito Token") :
#         # If refresh token button is clicked or the token is expired, refresh the token
#         token = oauth2.refresh_token(token, force=True)
#         # Put the refresh token in the session state as it is not returned by Cognito
#         token["refresh_token"] = refresh_token
#         # Retrieve the Identity Center token

#         st.session_state.token = token
#         st.rerun()

#     if "idc_jwt_token" not in st.session_state:
#         st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(token["id_token"])
#         st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + \
#             timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
#     elif st.session_state["idc_jwt_token"]["expires_at"] < datetime.now(UTC):
#         # If the Identity Center token is expired, refresh the Identity Center token
#         try:
#             st.session_state["idc_jwt_token"] = utils.refresh_iam_oidc_token(
#                 st.session_state["idc_jwt_token"]["refreshToken"]
#                 )
#             st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + \
#                 timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
#         except Exception as e:
#             st.error(f"Error refreshing Identity Center token: {e}. Please reload the page.")

#     col1, col2 = st.columns([1,1])

#     with col1:
#         st.write("Welcome: ", user_email)
#     with col2:
#         st.button("Clear Chat History", on_click=clear_chat_history)

#     # Initialize the chat messages in the session state if it doesn't exist
#     if "messages" not in st.session_state:
#         st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]

#     if "conversationId" not in st.session_state:
#         st.session_state["conversationId"] = ""

#     if "parentMessageId" not in st.session_state:
#         st.session_state["parentMessageId"] = ""

#     if "chat_history" not in st.session_state:
#         st.session_state["chat_history"] = []

#     if "questions" not in st.session_state:
#         st.session_state.questions = []

#     if "answers" not in st.session_state:
#         st.session_state.answers = []

#     if "input" not in st.session_state:
#         st.session_state.input = ""


#     # Display the chat messages
#     for message in st.session_state.messages:
#         with st.chat_message(message["role"]):
#             st.write(message["content"])


#     # User-provided prompt
#     if prompt := st.chat_input():
#         st.session_state.messages.append({"role": "user", "content": prompt})
#         with st.chat_message("user"):
#             st.write(prompt)


#     # If the last message is from the user, generate a response from the Q_backend
#     if st.session_state.messages[-1]["role"] != "assistant":
#         with st.chat_message("assistant"):
#             with st.spinner("Thinking..."):
#                 placeholder = st.empty()
#                 response = utils.get_queue_chain(prompt,st.session_state["conversationId"],
#                                                  st.session_state["parentMessageId"],
#                                                  st.session_state["idc_jwt_token"]["idToken"])
#                 if "references" in response:
#                     full_response = f"""{response["answer"]}\n\n---\n{response["references"]}"""
#                 else:
#                     full_response = f"""{response["answer"]}\n\n---\nNo sources"""
#                 placeholder.markdown(full_response)
#                 st.session_state["conversationId"] = response["conversationId"]
#                 st.session_state["parentMessageId"] = response["parentMessageId"]


#         st.session_state.messages.append({"role": "assistant", "content": full_response})
#         feedback = streamlit_feedback(
#             feedback_type="thumbs",
#             optional_text_label="[Optional] Please provide an explanation",
#         )

# def main():
#     navigation_bar()

# if __name__ == "__main__":
#     main()
    